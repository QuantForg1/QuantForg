"use client";

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/execution/confirm-dialog";
import {
  PreTradeChecklist,
  preTradeAllowsExecution,
} from "@/components/execution/pre-trade-checklist";
import { AiDecisionCard } from "@/components/execution/ai-decision-card";
import {
  EMPTY_EXECUTION_METRICS,
  metricsFromPipelineResult,
  type ExecutionTimingMetrics,
} from "@/components/execution/execution-metrics-strip";
import { formatRiskRejection } from "@/components/execution/risk-rules-panel";
import { executionApi, mt5Api, riskApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, num, str } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import {
  MULTI_SYMBOL_ENABLED,
  resolveTradingSymbol,
} from "@/lib/trading/gold-only";
import { humanExecutionError } from "@/lib/execution/humanize";
import { saveLastExecutionMetrics } from "@/lib/execution/last-metrics";
import { invalidatePostTrade } from "@/lib/execution/post-trade-invalidate";
import { recordAudit } from "@/lib/observability/audit";
import { captureError } from "@/lib/observability/error-monitor";
import { isReadOnlyMode } from "@/lib/platform/beta";
import {
  formatSubmitFailure,
  type ExecutionStageId,
} from "@/lib/execution/submit-errors";
import {
  contractSizeForSymbol,
  lotsFromRiskBudget,
  stopLossDistance,
  type SizingMode,
} from "@/lib/execution/position-sizing";

const ORDER_TYPES = ["market", "limit", "stop", "stop_limit"] as const;
const VOLUMES = ["0.01", "0.05", "0.10", "0.50", "1.00"];

type OrderType = (typeof ORDER_TYPES)[number];

export type OrderTicketHandle = {
  buy: () => void;
  sell: () => void;
  cancelDialog: () => void;
};

export const ExecutionOrderTicket = forwardRef<
  OrderTicketHandle,
  {
    symbol: string;
    onSymbolChange: (s: string) => void;
    connected: boolean;
    bid?: number;
    ask?: number;
    /** Epoch ms of last broker tick — reject submit when stale. */
    tickTimeMs?: number | null;
    dense?: boolean;
  }
>(function ExecutionOrderTicket(
  { symbol, onSymbolChange, connected, bid, ask, tickTimeMs = null, dense = false },
  ref,
) {
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [volume, setVolume] = useState("0.01");
  const [sizingMode, setSizingMode] = useState<SizingMode>("percentage_risk");
  const [price, setPrice] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [riskPct, setRiskPct] = useState("1");
  const [comment, setComment] = useState("");
  const [trailingStop, setTrailingStop] = useState("");
  const [breakEven, setBreakEven] = useState(false);
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmMode, setConfirmMode] = useState<"oneclick" | "ticket">("ticket");
  const [lastCheck, setLastCheck] = useState<Record<string, unknown> | null>(null);
  const [lastRisk, setLastRisk] = useState<Record<string, unknown> | null>(null);
  const [calc, setCalc] = useState<Record<string, unknown> | null>(null);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);
  const [execMetrics, setExecMetrics] = useState<ExecutionTimingMetrics>(
    EMPTY_EXECUTION_METRICS,
  );
  const [execFlash, setExecFlash] = useState(false);
  const [execStage, setExecStage] = useState<ExecutionStageId>("idle");
  const [rejectReason, setRejectReason] = useState<string | undefined>();
  const session = useTradingSession();
  const qc = useQueryClient();

  const accountQ = useQuery({
    queryKey: ["mt5-account"],
    queryFn: mt5Api.account,
    retry: false,
    enabled: connected,
    staleTime: 15_000,
  });
  const equity = num(asRecord(accountQ.data).equity) || num(session.equity);

  const mid =
    Number.isFinite(bid) && Number.isFinite(ask) && bid != null && ask != null
      ? (bid + ask) / 2
      : NaN;
  const spread =
    Number.isFinite(bid) && Number.isFinite(ask) && bid != null && ask != null
      ? ask - bid
      : NaN;

  const needsPrice = orderType !== "market";
  const entryForSize =
    needsPrice && num(price) > 0
      ? num(price)
      : Number.isFinite(mid)
        ? mid
        : NaN;
  const slDist = stopLossDistance(entryForSize, num(stopLoss, NaN));

  const buildPayload = () => {
    const parts = [comment.trim() || "quantforg-execution"];
    if (trailingStop.trim()) parts.push(`trail:${trailingStop.trim()}`);
    if (breakEven) parts.push("be:1");
    return {
      request_id: `exec_${crypto.randomUUID()}`,
      symbol: symbol.trim().toUpperCase(),
      side,
      order_type: orderType,
      volume,
      price: price || null,
      stop_loss: stopLoss || null,
      take_profit: takeProfit || null,
      slippage: 10,
      magic: 0,
      comment: parts.join(" | ").slice(0, 31),
    };
  };

  const riskCheckBody = (payload: ReturnType<typeof buildPayload>) => {
    const liveSpread =
      Number.isFinite(bid) && Number.isFinite(ask) && bid != null && ask != null
        ? String(ask - bid)
        : undefined;
    return {
      request_id: payload.request_id,
      symbol: payload.symbol,
      side: payload.side,
      requested_lots:
        sizingMode === "fixed_lot" ? payload.volume : undefined,
      entry_price: payload.price || String(mid || 1),
      stop_loss_distance: slDist != null ? String(slDist) : undefined,
      sizing_method: sizingMode,
      risk_per_trade_pct:
        sizingMode === "percentage_risk" ? riskPct : undefined,
      spread: liveSpread,
      equity: connected ? undefined : Number.isFinite(equity) ? String(equity) : undefined,
    };
  };

  /** Sync lot size from equity · risk% · SL distance (percentage_risk mode). */
  useEffect(() => {
    if (sizingMode !== "percentage_risk" || !connected) return;
    if (slDist == null || !Number.isFinite(equity) || equity <= 0) return;
    const pct = num(riskPct, NaN);
    if (!Number.isFinite(pct) || pct <= 0) return;
    const lots = lotsFromRiskBudget({
      equity,
      riskPct: pct,
      stopDistance: slDist,
      contractSize: contractSizeForSymbol(symbol),
    });
    if (lots == null) return;
    const next = lots.toFixed(2);
    setVolume((prev) => (prev === next ? prev : next));
  }, [sizingMode, connected, equity, riskPct, slDist, symbol]);

  const refreshEstimates = async () => {
    if (!connected || !symbol) return;
    try {
      const payload = buildPayload();
      // Dense terminal: calculate only — validate runs on safety/submit.
      if (dense) {
        const c = await mt5Api.calculateOrder(payload);
        setCalc(asRecord(c));
        return;
      }
      const [v, c] = await Promise.all([
        mt5Api.validateOrder(payload),
        mt5Api.calculateOrder(payload),
      ]);
      setValidation(asRecord(v));
      setCalc(asRecord(c));
    } catch (e) {
      setValidation(null);
      setCalc(null);
      if (e instanceof ApiError) {
        toast.error(e.message);
      }
    }
  };

  useEffect(() => {
    if (!connected || !symbol) return;
    const t = window.setTimeout(() => {
      void refreshEstimates();
    }, dense ? 700 : 400);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, symbol, side, orderType, volume, price, stopLoss, takeProfit, dense]);

  const positionSizeHint = () => {
    if (!Number.isFinite(equity) || equity <= 0) return "—";
    const pct = num(riskPct, 1) / 100;
    if (!Number.isFinite(pct)) return "—";
    return formatCurrency(equity * pct);
  };

  const runSafety = async () => {
    setBusy(true);
    try {
      const payload = buildPayload();
      const v = await mt5Api.validateOrder(payload);
      setValidation(asRecord(v));
      if (!v.valid) {
        const err = humanExecutionError(asRecord(v), "Order did not pass validation.");
        toast.error(err.title, { description: err.description });
        return;
      }
      const risk = await riskApi.check(riskCheckBody(payload));
      setLastRisk(asRecord(risk));
      const approved = str(asRecord(risk).approved_lots);
      if (
        sizingMode === "percentage_risk" &&
        approved &&
        Number.isFinite(Number(approved)) &&
        Number(approved) > 0
      ) {
        setVolume(Number(approved).toFixed(2));
      }
      const check = await executionApi.check({
        ...payload,
        volume:
          sizingMode === "percentage_risk" && approved
            ? Number(approved).toFixed(2)
            : payload.volume,
      });
      setLastCheck(asRecord(check));
      toast.success(`Safety: ${str(asRecord(check).decision)}`);
      if (asListish(asRecord(risk).warnings).length) {
        toast.message("Risk warnings", {
          description: asListish(asRecord(risk).warnings).slice(0, 2).join(" · "),
        });
      }
      if (str(asRecord(risk).decision).toUpperCase() === "REJECT") {
        toast.error("Risk engine blocked this order", {
          description: formatRiskRejection(asRecord(risk)),
        });
      }
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Safety check failed");
    } finally {
      setBusy(false);
    }
  };

  const oneClick = (nextSide: "buy" | "sell") => {
    setSide(nextSide);
    setOrderType("market");
    setConfirmMode("oneclick");
    setExecStage("idle");
    setRejectReason(undefined);
    if (!connected) {
      toast.error("Broker disconnected — trading disabled");
      return;
    }
    setConfirmOpen(true);
  };

  useImperativeHandle(
    ref,
    () => ({
      buy: () => oneClick("buy"),
      sell: () => oneClick("sell"),
      cancelDialog: () => {
        setConfirmOpen(false);
        setExecStage("idle");
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [connected, symbol, volume],
  );

  const submitLive = async () => {
    setBusy(true);
    setExecStage("validating");
    setRejectReason(undefined);
    const t0 = performance.now();
    let signalMs: number | undefined;
    let riskMs: number | undefined;
    let orderCheckMs: number | undefined;
    try {
      if (isReadOnlyMode()) {
        setExecStage("rejected");
        setRejectReason("Read-only mode is enabled — live orders are blocked");
        toast.error("Read-only mode is enabled — live orders are blocked");
        return;
      }

      // Refresh quote if stale before blocking — reduces false rejects.
      let tickAgeOk =
        tickTimeMs != null &&
        Number.isFinite(tickTimeMs) &&
        Date.now() - tickTimeMs <= 5_000;
      if (!tickAgeOk && connected && symbol) {
        try {
          await mt5Api.tick(symbol);
          tickAgeOk = true;
        } catch {
          /* fall through to stale check */
        }
      }
      if (!tickAgeOk) {
        setExecStage("rejected");
        setRejectReason("Market price is stale — refresh quote before sending");
        toast.error("Market price is stale — refresh quote before sending");
        return;
      }

      let payload = {
        ...buildPayload(),
        side,
        order_type: confirmMode === "oneclick" ? "market" : orderType,
      };

      const tSignal = performance.now();
      // Validate + risk in parallel to cut submit latency.
      const [v, risk] = await Promise.all([
        mt5Api.validateOrder(payload),
        riskApi.check(riskCheckBody(payload)),
      ]);
      signalMs = performance.now() - tSignal;
      riskMs = signalMs;
      setValidation(asRecord(v));
      setLastRisk(asRecord(risk));

      if (!v.valid) {
        const err = humanExecutionError(
          asRecord(v),
          "Order did not pass broker validation.",
        );
        setExecStage("rejected");
        setRejectReason([err.title, err.description].filter(Boolean).join(" — "));
        toast.error(err.title, { description: err.description });
        return;
      }

      setExecStage("risk");
      const riskDecision = str(asRecord(risk).decision).toUpperCase();
      if (riskDecision === "REJECT") {
        const detail = formatRiskRejection(asRecord(risk));
        setExecStage("rejected");
        setRejectReason(detail || "Risk engine blocked execution");
        toast.error("Risk engine blocked execution", {
          description: detail,
        });
        return;
      }

      const approvedLots = str(asRecord(risk).approved_lots);
      const sizedVolume =
        sizingMode === "percentage_risk" &&
        approvedLots &&
        Number.isFinite(Number(approvedLots)) &&
        Number(approvedLots) > 0
          ? Number(approvedLots).toFixed(2)
          : payload.volume;
      if (sizedVolume !== payload.volume) {
        setVolume(sizedVolume);
        payload = { ...payload, volume: sizedVolume };
      }

      const gateOk = preTradeAllowsExecution(
        {
          symbol: payload.symbol,
          volume: payload.volume,
          bid,
          ask,
          stopLoss: stopLoss || undefined,
          takeProfit: takeProfit || undefined,
          validationValid: true,
          riskDecision,
          riskAssessment: asRecord(risk),
          marginRequired: str(asRecord(calc).expected_margin, ""),
        },
        session,
      );
      if (!gateOk) {
        const reason =
          !session.gatewayOnline || !session.connected
            ? "Gateway or broker session is offline"
            : "Pre-trade checklist failed — check spread, margin, and risk";
        setExecStage("rejected");
        setRejectReason(reason);
        toast.error(reason);
        return;
      }

      setExecStage("sending");
      const liveSpread =
        Number.isFinite(bid) && Number.isFinite(ask) && bid != null && ask != null
          ? String(ask - bid)
          : undefined;
      const tCheck = performance.now();
      const check = await executionApi.check(payload);
      orderCheckMs = performance.now() - tCheck;
      setLastCheck(asRecord(check));
      if (str(asRecord(check).decision) === "reject") {
        const err = humanExecutionError(asRecord(check), "Execution rejected");
        recordAudit("order_submit", "failure", "Execution rejected by safety gate", {
          symbol: payload.symbol,
          side: payload.side,
        });
        setExecStage("rejected");
        setRejectReason([err.title, err.description].filter(Boolean).join(" — "));
        toast.error(err.title, { description: err.description });
        return;
      }

      setExecStage("broker");
      const tFill = performance.now();
      const result = await executionApi.submit({
        ...payload,
        signal_time_ms: signalMs,
        risk_time_ms: riskMs,
        order_check_time_ms: orderCheckMs,
        measured_spread: liveSpread,
      });
      const brokerFillMs = performance.now() - tFill;
      const totalMs = performance.now() - t0;
      const outcome = str(asRecord(result).outcome);
      const resultRec = asRecord(result);

      if (outcome === "success") {
        const fillPrice = num(resultRec.price, NaN);
        const measuredSlippage =
          Number.isFinite(fillPrice) && Number.isFinite(mid)
            ? String(Math.abs(fillPrice - mid))
            : undefined;
        const metrics = metricsFromPipelineResult(resultRec, {
          signalMs,
          riskMs,
          orderCheckMs,
          brokerFillMs,
          totalMs,
          spread: liveSpread,
          slippage: measuredSlippage,
        });
        setExecMetrics(metrics);
        saveLastExecutionMetrics(metrics);
        setExecFlash(true);
        window.setTimeout(() => setExecFlash(false), 450);
        setExecStage("completed");
        recordAudit("order_submit", "success", "Order submitted", {
          symbol: payload.symbol,
          side: payload.side,
          ticket: str(resultRec.order_ticket),
        });
        const ticket = str(resultRec.order_ticket, "—");
        const fill = str(resultRec.price, "");
        toast.success("Order filled", {
          description: fill
            ? `Ticket ${ticket} · ${payload.side.toUpperCase()} ${payload.volume} @ ${fill}`
            : `Ticket ${ticket} · ${payload.side.toUpperCase()} ${payload.volume}`,
        });
        try {
          await session.invalidateAll();
          await invalidatePostTrade(qc);
        } catch {
          /* never mask a successful fill as submit failure */
        }
        window.setTimeout(() => setConfirmOpen(false), 600);
        return;
      }

      if (outcome === "disabled") {
        const msg = str(
          resultRec.message,
          "Live send disabled — set EXECUTION_ENABLED=true with MT5 gateway configured.",
        );
        recordAudit("order_submit", "info", "Live send disabled by EXECUTION_ENABLED", {
          symbol: payload.symbol,
        });
        setExecStage("rejected");
        setRejectReason(msg);
        toast.message("Live send disabled", { description: msg });
        return;
      }

      const err = humanExecutionError(
        resultRec,
        resultRec.retryable
          ? "Order submit failed — retryable"
          : "Order rejected by MT5",
      );
      recordAudit("order_submit", "failure", "Order submit failed", {
        symbol: payload.symbol,
        outcome,
      });
      setExecStage("rejected");
      setRejectReason([err.title, err.description].filter(Boolean).join(" — "));
      toast.error(err.title, {
        description: err.description || str(resultRec.message) || undefined,
      });
    } catch (e) {
      recordAudit("order_submit", "failure", "Order submit exception");
      captureError("execution", e, { path: "/execution/submit" });
      const formatted = formatSubmitFailure(e);
      setExecStage("rejected");
      setRejectReason(
        [formatted.title, formatted.description].filter(Boolean).join(" — "),
      );
      toast.error(formatted.title, { description: formatted.description });
    } finally {
      setBusy(false);
    }
  };

  const margin = str(asRecord(calc).expected_margin ?? asRecord(validation).expected_margin, "—");
  const estProfit = str(
    asRecord(calc).estimated_profit ?? asRecord(validation).estimated_profit,
    "—",
  );
  const snapshot = asRecord(asRecord(calc).request_snapshot ?? asRecord(validation).request_snapshot);
  const commission = str(snapshot.commission ?? snapshot.estimated_commission, "—");
  const swap = str(snapshot.swap ?? snapshot.estimated_swap, "—");

  const entryPx = Number.isFinite(entryForSize) ? entryForSize : NaN;
  const slPx = num(stopLoss, NaN);
  const tpPx = num(takeProfit, NaN);
  const riskReward =
    Number.isFinite(entryPx) &&
    Number.isFinite(slPx) &&
    Number.isFinite(tpPx) &&
    Math.abs(entryPx - slPx) > 0
      ? Math.abs(tpPx - entryPx) / Math.abs(entryPx - slPx)
      : null;
  const riskBudgetPct = Math.min(100, Math.max(4, num(riskPct, 1) * 12));
  const rewardBudgetPct =
    riskReward != null ? Math.min(100, Math.max(4, riskBudgetPct * Math.min(riskReward, 4))) : riskBudgetPct;

  return (
    <div
      className={cn(
        dense ? "border-0" : "rounded-lg border border-[var(--border)]",
        execFlash && "qf-exec-flash",
      )}
      aria-busy={busy}
    >
      {!dense ? (
        <div className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-4 py-3">
          <h2 className="text-sm font-semibold tracking-tight">Order Ticket</h2>
          <Badge tone={connected ? "success" : "warning"}>
            {connected ? "Ready" : "Disabled"}
          </Badge>
        </div>
      ) : null}
      <div className={cn("space-y-3", dense ? "space-y-2.5 px-3 py-2.5" : "space-y-4 p-4")}>
        {/* Quote + side */}
        <div className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            disabled={!connected || busy}
            onClick={() => void oneClick("buy")}
            aria-label="Buy market"
            className={cn(
              "flex flex-col items-center justify-center rounded-md border px-2 py-2.5 transition-colors duration-[var(--duration-os)] ease-[var(--ease-os)]",
              "border-[var(--buy)]/40 bg-[var(--buy)]/10 text-[var(--buy)]",
              "hover:bg-[var(--buy)]/20 disabled:opacity-40",
              dense ? "min-h-[3.25rem]" : "min-h-14",
            )}
          >
            <span className="text-[10px] uppercase tracking-wider opacity-80">Buy</span>
            <span className="tabular text-sm font-semibold">
              {Number.isFinite(ask) && ask != null ? formatNumber(ask, 2) : "—"}
            </span>
          </button>
          <button
            type="button"
            disabled={!connected || busy}
            onClick={() => void oneClick("sell")}
            aria-label="Sell market"
            className={cn(
              "flex flex-col items-center justify-center rounded-md border px-2 py-2.5 transition-colors duration-[var(--duration-os)] ease-[var(--ease-os)]",
              "border-[var(--sell)]/40 bg-[var(--sell)]/10 text-[var(--sell)]",
              "hover:bg-[var(--sell)]/20 disabled:opacity-40",
              dense ? "min-h-[3.25rem]" : "min-h-14",
            )}
          >
            <span className="text-[10px] uppercase tracking-wider opacity-80">Sell</span>
            <span className="tabular text-sm font-semibold">
              {Number.isFinite(bid) && bid != null ? formatNumber(bid, 2) : "—"}
            </span>
          </button>
        </div>

        <AiDecisionCard
          symbol={symbol}
          side={side}
          volume={volume}
          entryPrice={mid}
          stopLoss={stopLoss || undefined}
          takeProfit={takeProfit || undefined}
          compact={dense}
        />

        {/* Live risk / reward preview */}
        <div className="rounded-md border border-[var(--border)]/80 bg-[var(--surface-2)]/70 p-2.5">
          <div className="mb-1.5 flex items-center justify-between text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            <span>Risk</span>
            <span className="tabular text-[var(--fg)]">{positionSizeHint()}</span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-[var(--surface)]">
            <div
              className="h-full rounded-full bg-[var(--danger)]/80 transition-[width] duration-[var(--duration-os)] ease-[var(--ease-os)]"
              style={{ width: `${riskBudgetPct}%` }}
            />
          </div>
          <div className="mb-1.5 mt-2 flex items-center justify-between text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            <span>Reward</span>
            <span className="tabular text-[var(--fg)]">
              {riskReward != null ? `1 : ${formatNumber(riskReward, 2)}` : "Set SL / TP"}
            </span>
          </div>
          <div className="h-1 overflow-hidden rounded-full bg-[var(--surface)]">
            <div
              className="h-full rounded-full bg-[var(--success)]/80 transition-[width] duration-[var(--duration-os)] ease-[var(--ease-os)]"
              style={{ width: `${rewardBudgetPct}%` }}
            />
          </div>
          <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
            <Est label="Spread" value={Number.isFinite(spread) ? formatNumber(spread, 5) : "—"} />
            <Est label="Margin" value={margin === "—" ? "—" : formatMaybeMoney(margin)} />
            <Est
              label="Safety"
              value={lastCheck ? str(lastCheck.decision) : "—"}
            />
          </div>
          {execMetrics.source === "live" && execMetrics.totalMs != null ? (
            <p className="mt-2 text-[10px] text-[var(--fg-subtle)]" aria-live="polite">
              Last fill · {formatNumber(execMetrics.totalMs, 0)} ms
            </p>
          ) : null}
        </div>

        <PreTradeChecklist
          inputs={{
            symbol,
            volume,
            bid,
            ask,
            stopLoss: stopLoss || undefined,
            takeProfit: takeProfit || undefined,
            validationValid:
              validation == null ? null : Boolean(validation.valid),
            riskDecision: lastRisk ? str(lastRisk.decision).toUpperCase() : null,
            riskAssessment: lastRisk,
            marginRequired: str(asRecord(calc).expected_margin, ""),
          }}
          compact
        />

        <div className="grid gap-2 grid-cols-2">
          {MULTI_SYMBOL_ENABLED ? (
            <div className="space-y-1 col-span-2">
              <Label htmlFor="exec-symbol" className="text-[11px]">Symbol</Label>
              <Input
                id="exec-symbol"
                className="h-9"
                value={symbol}
                onChange={(e) => onSymbolChange(resolveTradingSymbol(e.target.value))}
                disabled={!connected}
              />
            </div>
          ) : null}
          <div className="space-y-1">
            <Label htmlFor="exec-type" className="text-[11px]">Type</Label>
            <select
              id="exec-type"
              className="flex h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm"
              value={orderType}
              onChange={(e) => setOrderType(e.target.value as OrderType)}
              disabled={!connected}
            >
              {ORDER_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace("_", " ")}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="exec-side" className="text-[11px]">Side</Label>
            <select
              id="exec-side"
              className="flex h-9 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 text-sm"
              value={side}
              onChange={(e) => setSide(e.target.value as "buy" | "sell")}
              disabled={!connected}
            >
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </div>

          <div className="col-span-2 space-y-1">
            <div className="flex items-center justify-between">
              <Label className="text-[11px]">Sizing</Label>
              <div className="flex gap-1">
                <Button
                  type="button"
                  size="sm"
                  className="h-6 px-2 text-[10px]"
                  variant={sizingMode === "percentage_risk" ? "default" : "secondary"}
                  onClick={() => setSizingMode("percentage_risk")}
                  disabled={!connected}
                >
                  Risk %
                </Button>
                <Button
                  type="button"
                  size="sm"
                  className="h-6 px-2 text-[10px]"
                  variant={sizingMode === "fixed_lot" ? "default" : "secondary"}
                  onClick={() => setSizingMode("fixed_lot")}
                  disabled={!connected}
                >
                  Fixed
                </Button>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Input
                id="exec-risk"
                className="h-9"
                value={riskPct}
                onChange={(e) => setRiskPct(e.target.value)}
                disabled={!connected}
                aria-label="Risk percent"
                placeholder="Risk %"
              />
              <Input
                id="exec-volume"
                className="h-9"
                value={volume}
                onChange={(e) => {
                  setSizingMode("fixed_lot");
                  setVolume(e.target.value);
                }}
                disabled={!connected || sizingMode === "percentage_risk"}
                readOnly={sizingMode === "percentage_risk"}
                aria-label="Volume lots"
              />
            </div>
            {sizingMode === "fixed_lot" ? (
              <div className="flex flex-wrap gap-1">
                {VOLUMES.map((v) => (
                  <Button
                    key={v}
                    type="button"
                    size="sm"
                    className="h-6 px-2 text-[10px]"
                    variant={volume === v ? "default" : "secondary"}
                    onClick={() => {
                      setSizingMode("fixed_lot");
                      setVolume(v);
                    }}
                    disabled={!connected}
                  >
                    {v}
                  </Button>
                ))}
              </div>
            ) : null}
          </div>

          {needsPrice ? (
            <div className="col-span-2 space-y-1">
              <Label htmlFor="exec-price" className="text-[11px]">
                {orderType === "stop_limit" ? "Trigger / limit" : "Price"}
              </Label>
              <Input
                id="exec-price"
                className="h-9"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={Number.isFinite(mid) ? formatNumber(mid, 5) : "0.00000"}
                disabled={!connected}
              />
            </div>
          ) : null}

          <div className="space-y-1">
            <Label htmlFor="exec-sl" className="text-[11px]">Stop loss</Label>
            <Input
              id="exec-sl"
              className="h-9"
              value={stopLoss}
              onChange={(e) => setStopLoss(e.target.value)}
              disabled={!connected}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="exec-tp" className="text-[11px]">Take profit</Label>
            <Input
              id="exec-tp"
              className="h-9"
              value={takeProfit}
              onChange={(e) => setTakeProfit(e.target.value)}
              disabled={!connected}
            />
          </div>

          {!dense ? (
            <>
              <div className="space-y-1">
                <Label htmlFor="exec-trail" className="text-[11px]">Trailing</Label>
                <Input
                  id="exec-trail"
                  className="h-9"
                  value={trailingStop}
                  onChange={(e) => setTrailingStop(e.target.value)}
                  placeholder="points"
                  disabled={!connected}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="exec-comment" className="text-[11px]">Comment</Label>
                <Input
                  id="exec-comment"
                  className="h-9"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  disabled={!connected}
                  maxLength={24}
                />
              </div>
              <label className="col-span-2 flex items-center gap-2 text-xs text-[var(--fg-muted)]">
                <input
                  type="checkbox"
                  checked={breakEven}
                  onChange={(e) => setBreakEven(e.target.checked)}
                  disabled={!connected}
                />
                Break even tag
              </label>
            </>
          ) : null}
        </div>

        {!dense ? (
          <div className="grid grid-cols-2 gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 text-xs sm:grid-cols-4">
            <Est label="Est. commission" value={commission} />
            <Est label="Est. swap" value={swap} />
            <Est label="Est. profit" value={estProfit === "—" ? "—" : formatMaybeMoney(estProfit)} />
            <Est
              label="Validation"
              value={
                validation ? (validation.valid ? "Valid" : "Invalid") : "—"
              }
            />
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="secondary"
            className="h-9"
            disabled={!connected || busy}
            onClick={() => void runSafety()}
          >
            Validate
          </Button>
          <Button
            className="h-9"
            disabled={!connected || busy}
            onClick={() => {
              setConfirmMode("ticket");
              setExecStage("idle");
              setRejectReason(undefined);
              setConfirmOpen(true);
            }}
          >
            Submit
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={(open) => {
          setConfirmOpen(open);
          if (!open) {
            setExecStage("idle");
            setRejectReason(undefined);
          }
        }}
        title={`${side.toUpperCase()} ${symbol}`}
        description={`Submit ${confirmMode === "oneclick" ? "market" : orderType} ${side} ${volume} lots via the Execution Gateway. Live fills only occur when EXECUTION_ENABLED is true.`}
        confirmLabel="Confirm submit"
        tone={side === "sell" ? "danger" : "default"}
        busy={busy}
        stage={execStage}
        rejectReason={rejectReason}
        onConfirm={submitLive}
      />
    </div>
  );
});

function Est({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-[var(--fg-subtle)]">{label}</p>
      <p className="tabular text-[11px] font-medium text-[var(--fg)]">{value}</p>
    </div>
  );
}

function formatMaybeMoney(v: string) {
  const n = Number(v);
  return Number.isFinite(n) ? formatCurrency(n) : v;
}

function asListish(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map(String);
}

/** Legacy export name for existing imports */
export { ExecutionOrderTicket as OrderTicket };
