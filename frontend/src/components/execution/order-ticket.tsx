"use client";

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
  TRADING_SYMBOL,
  resolveTradingSymbol,
} from "@/lib/trading/gold-only";
import { humanExecutionError } from "@/lib/execution/humanize";
import { saveLastExecutionMetrics } from "@/lib/execution/last-metrics";
import Link from "next/link";
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
    dense?: boolean;
  }
>(function ExecutionOrderTicket(
  { symbol, onSymbolChange, connected, bid, ask, dense = false },
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
      request_id: `exec_${Date.now()}`,
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
      cancelDialog: () => setConfirmOpen(false),
    }),
    // oneClick closes over latest connected/side state via setState
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [connected, symbol, volume],
  );

  const submitLive = async () => {
    setBusy(true);
    const t0 = performance.now();
    let signalMs: number | undefined;
    let riskMs: number | undefined;
    let orderCheckMs: number | undefined;
    try {
      const { isReadOnlyMode } = await import("@/lib/platform/beta");
      if (isReadOnlyMode()) {
        toast.error("Read-only mode is enabled — live orders are blocked");
        return;
      }
      let payload = {
        ...buildPayload(),
        side: confirmMode === "oneclick" ? side : side,
        order_type: confirmMode === "oneclick" ? "market" : orderType,
      };
      const tSignal = performance.now();
      const v = await mt5Api.validateOrder(payload);
      signalMs = performance.now() - tSignal;
      setValidation(asRecord(v));
      if (!v.valid) {
        const err = humanExecutionError(asRecord(v), "Order did not pass validation.");
        toast.error(err.title, { description: err.description });
        return;
      }
      const liveSpread =
        Number.isFinite(bid) && Number.isFinite(ask) && bid != null && ask != null
          ? String(ask - bid)
          : undefined;
      const tRisk = performance.now();
      const risk = await riskApi.check(riskCheckBody(payload));
      riskMs = performance.now() - tRisk;
      setLastRisk(asRecord(risk));
      const riskDecision = str(asRecord(risk).decision).toUpperCase();
      if (riskDecision === "REJECT") {
        const detail = formatRiskRejection(asRecord(risk));
        const err = humanExecutionError(
          {
            message: "Risk engine blocked execution",
            rejection_reasons: asListish(asRecord(risk).reasons).length
              ? asListish(asRecord(risk).reasons)
              : [detail],
          },
          "Risk engine blocked execution",
        );
        toast.error(err.title, { description: detail || err.description });
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
        toast.error("Pre-trade checklist failed — execution blocked");
        return;
      }
      const tCheck = performance.now();
      const check = await executionApi.check(payload);
      orderCheckMs = performance.now() - tCheck;
      setLastCheck(asRecord(check));
      if (str(asRecord(check).decision) === "reject") {
        const { recordAudit } = await import("@/lib/observability/audit");
        recordAudit("order_submit", "failure", "Execution rejected by safety gate", {
          symbol: payload.symbol,
          side: payload.side,
        });
        const err = humanExecutionError(asRecord(check), "Execution rejected");
        toast.error(err.title, { description: err.description });
        return;
      }
      const result = await executionApi.submit(payload);
      const totalMs = performance.now() - t0;
      const outcome = str(asRecord(result).outcome);
      if (outcome === "success") {
        const metrics = metricsFromPipelineResult(asRecord(result), {
          signalMs,
          riskMs,
          orderCheckMs,
          totalMs,
          spread: liveSpread,
        });
        setExecMetrics(metrics);
        saveLastExecutionMetrics(metrics);
      }
      const { recordAudit } = await import("@/lib/observability/audit");
      if (outcome === "disabled") {
        recordAudit("order_submit", "info", "Live send disabled by EXECUTION_ENABLED", {
          symbol: payload.symbol,
        });
        toast.message("Live send disabled", {
          description: str(
            asRecord(result).message,
            "Set EXECUTION_ENABLED=true on the API with MT5 gateway configured.",
          ),
        });
      } else if (outcome === "success") {
        recordAudit("order_submit", "success", "Order submitted", {
          symbol: payload.symbol,
          side: payload.side,
          ticket: str(asRecord(result).order_ticket),
        });
        const ticket = str(asRecord(result).order_ticket, "—");
        const fillPrice = str(asRecord(result).price, "");
        toast.success("Order filled", {
          description: fillPrice
            ? `Ticket ${ticket} · ${payload.side.toUpperCase()} ${payload.volume} @ ${fillPrice}`
            : `Ticket ${ticket} · ${payload.side.toUpperCase()} ${payload.volume}`,
        });
        await session.invalidateAll();
        const { invalidatePostTrade } = await import("@/lib/execution/post-trade-invalidate");
        await invalidatePostTrade(qc);
      } else if (asRecord(result).retryable) {
        recordAudit("order_submit", "failure", "Order submit retryable failure", {
          symbol: payload.symbol,
          outcome,
        });
        const err = humanExecutionError(asRecord(result), outcome);
        toast.error(err.title, {
          description: err.description || "Retryable — try again.",
        });
      } else {
        recordAudit("order_submit", "failure", "Order submit failed", {
          symbol: payload.symbol,
          outcome,
        });
        const err = humanExecutionError(asRecord(result), "Order rejected by MT5");
        toast.error(err.title, { description: err.description });
      }
      setConfirmOpen(false);
    } catch (e) {
      const { recordAudit } = await import("@/lib/observability/audit");
      const { captureError } = await import("@/lib/observability/error-monitor");
      recordAudit("order_submit", "failure", "Order submit exception");
      captureError("execution", e, { path: "/execution/submit" });
      if (e instanceof ApiError) {
        const detail =
          e.status === 403
            ? "Execution may be disabled — set EXECUTION_ENABLED=true with a live MT5 gateway."
            : e.code
              ? `Code ${e.code}`
              : undefined;
        toast.error(e.message || "Submit failed", { description: detail });
      } else {
        toast.error("Submit failed");
      }
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

  return (
    <Card className={cn(dense && "border-0 shadow-none")}>
      <CardHeader
        className={cn(
          "flex-row items-center justify-between gap-2",
          dense && "px-3 py-2",
        )}
      >
        <CardTitle className={cn(dense && "text-sm")}>Order Ticket</CardTitle>
        <Badge tone={connected ? "success" : "warning"}>
          {connected ? "Ready" : "Disabled"}
        </Badge>
      </CardHeader>
      <CardContent className={cn("space-y-4", dense && "space-y-2.5 px-2.5 pb-2.5")}>
        <div className="grid grid-cols-2 gap-2">
          <Button
            className={cn("font-semibold", dense ? "h-10 text-sm" : "h-12 text-base")}
            disabled={!connected || busy}
            onClick={() => void oneClick("buy")}
            aria-label="Buy market"
          >
            BUY
          </Button>
          <Button
            className={cn("font-semibold", dense ? "h-10 text-sm" : "h-12 text-base")}
            variant="danger"
            disabled={!connected || busy}
            onClick={() => void oneClick("sell")}
            aria-label="Sell market"
          >
            SELL
          </Button>
        </div>

        <AiDecisionCard
          symbol={symbol}
          side={side}
          volume={volume}
          entryPrice={mid}
          stopLoss={stopLoss || undefined}
          takeProfit={takeProfit || undefined}
        />

        {execMetrics.source === "live" ? (
          <p className="text-[10px] text-[var(--fg-subtle)]">
            Last fill · total{" "}
            {execMetrics.totalMs != null
              ? `${formatNumber(execMetrics.totalMs, 0)} ms`
              : "—"}
            {" · "}
            <Link href="/monitoring" className="text-[var(--accent)] hover:underline">
              Execution metrics
            </Link>
          </p>
        ) : (
          <p className="text-[10px] text-[var(--fg-subtle)]">
            <Link href="/monitoring" className="text-[var(--accent)] hover:underline">
              Monitoring
            </Link>
            {" · "}
            <Link href="/analytics" className="text-[var(--accent)] hover:underline">
              Analytics
            </Link>
            {" · "}
            <Link href="/risk-center" className="text-[var(--accent)] hover:underline">
              Risk Center
            </Link>
          </p>
        )}

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

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="exec-symbol">Symbol</Label>
            <Input
              id="exec-symbol"
              value={MULTI_SYMBOL_ENABLED ? symbol : TRADING_SYMBOL}
              readOnly={!MULTI_SYMBOL_ENABLED}
              onChange={(e) => onSymbolChange(resolveTradingSymbol(e.target.value))}
              disabled={!connected}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="exec-side">Side</Label>
            <select
              id="exec-side"
              className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
              value={side}
              onChange={(e) => setSide(e.target.value as "buy" | "sell")}
              disabled={!connected}
            >
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="exec-type">Order type</Label>
            <select
              id="exec-type"
              className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
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
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Position sizing</Label>
            <div className="flex flex-wrap gap-1.5">
              <Button
                type="button"
                size="sm"
                variant={sizingMode === "percentage_risk" ? "default" : "secondary"}
                onClick={() => setSizingMode("percentage_risk")}
                disabled={!connected}
              >
                Risk %
              </Button>
              <Button
                type="button"
                size="sm"
                variant={sizingMode === "fixed_lot" ? "default" : "secondary"}
                onClick={() => setSizingMode("fixed_lot")}
                disabled={!connected}
              >
                Fixed lot
              </Button>
            </div>
            <p className="text-[10px] text-[var(--fg-subtle)]">
              {sizingMode === "percentage_risk"
                ? "Lots from equity × risk% ÷ (SL distance × contract size). Risk Engine is authoritative."
                : "Operator-selected fixed lot. Risk Engine still gates the order."}
            </p>
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="exec-volume">Volume</Label>
            <div className="flex flex-wrap gap-1.5">
              {VOLUMES.map((v) => (
                <Button
                  key={v}
                  type="button"
                  size="sm"
                  variant={volume === v && sizingMode === "fixed_lot" ? "default" : "secondary"}
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
            <Input
              id="exec-volume"
              className="mt-2"
              value={volume}
              onChange={(e) => {
                setSizingMode("fixed_lot");
                setVolume(e.target.value);
              }}
              disabled={!connected || sizingMode === "percentage_risk"}
              readOnly={sizingMode === "percentage_risk"}
            />
          </div>
          {needsPrice ? (
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="exec-price">
                {orderType === "stop_limit" ? "Trigger / limit price" : "Price"}
              </Label>
              <Input
                id="exec-price"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder={Number.isFinite(mid) ? formatNumber(mid, 5) : "0.00000"}
                disabled={!connected}
              />
            </div>
          ) : null}
          <div className="space-y-1.5">
            <Label htmlFor="exec-sl">Stop loss</Label>
            <Input
              id="exec-sl"
              value={stopLoss}
              onChange={(e) => setStopLoss(e.target.value)}
              disabled={!connected}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="exec-tp">Take profit</Label>
            <Input
              id="exec-tp"
              value={takeProfit}
              onChange={(e) => setTakeProfit(e.target.value)}
              disabled={!connected}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="exec-trail">Trailing stop</Label>
            <Input
              id="exec-trail"
              value={trailingStop}
              onChange={(e) => setTrailingStop(e.target.value)}
              placeholder="points"
              disabled={!connected}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="exec-comment">Order comment</Label>
            <Input
              id="exec-comment"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Optional (MT5 ≤31 chars)"
              disabled={!connected}
              maxLength={24}
            />
          </div>
          <label className="flex items-center gap-2 text-xs text-[var(--fg-muted)] sm:col-span-2">
            <input
              type="checkbox"
              checked={breakEven}
              onChange={(e) => setBreakEven(e.target.checked)}
              disabled={!connected}
            />
            Break even (tag order for SL→entry handling)
          </label>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="exec-risk">Risk per trade (%)</Label>
            <Input
              id="exec-risk"
              value={riskPct}
              onChange={(e) => setRiskPct(e.target.value)}
              disabled={!connected}
            />
            <p className="text-xs text-[var(--fg-subtle)]">
              {sizingMode === "percentage_risk"
                ? `Risk budget ≈ ${positionSizeHint()} · SL distance ${
                    slDist != null ? formatNumber(slDist, 2) : "—"
                  }`
                : `Fixed lot ${volume} · risk budget reference ≈ ${positionSizeHint()}`}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3 text-xs sm:grid-cols-4">
          <Est label="Spread" value={Number.isFinite(spread) ? formatNumber(spread, 5) : "—"} />
          <Est label="Margin required" value={margin === "—" ? "—" : formatMaybeMoney(margin)} />
          <Est label="Est. commission" value={commission} />
          <Est label="Est. swap" value={swap} />
          <Est label="Position size" value={volume} />
          <Est label="Est. profit" value={estProfit === "—" ? "—" : formatMaybeMoney(estProfit)} />
          <Est
            label="Validation"
            value={
              validation
                ? validation.valid
                  ? "Valid"
                  : "Invalid"
                : "—"
            }
          />
          <Est
            label="Safety"
            value={lastCheck ? str(lastCheck.decision) : "—"}
          />
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          <Button
            variant="secondary"
            disabled={!connected || busy}
            onClick={() => void runSafety()}
          >
            Validate & risk-check
          </Button>
          <Button
            disabled={!connected || busy}
            onClick={() => {
              setConfirmMode("ticket");
              setConfirmOpen(true);
            }}
          >
            Submit via gateway
          </Button>
        </div>
        <p className="text-[11px] text-[var(--fg-subtle)]">
          Live <code>order_send</code> remains gated by server <code>EXECUTION_ENABLED</code>. Stop
          limit uses the backend <code>stop_limit</code> order type when validation accepts it.
        </p>
      </CardContent>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={`${side.toUpperCase()} ${symbol}`}
        description={`Submit ${confirmMode === "oneclick" ? "market" : orderType} ${side} ${volume} lots via the Execution Gateway. Live fills only occur when EXECUTION_ENABLED is true.`}
        confirmLabel="Confirm submit"
        tone={side === "sell" ? "danger" : "default"}
        busy={busy}
        onConfirm={submitLive}
      />
    </Card>
  );
});

function Est({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[var(--fg-subtle)]">{label}</p>
      <p className="tabular font-medium text-[var(--fg)]">{value}</p>
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
