"use client";

import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useState,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/execution/confirm-dialog";
import { executionApi, mt5Api, riskApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord, num, str } from "@/lib/desk";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";

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
  const [price, setPrice] = useState("");
  const [stopLoss, setStopLoss] = useState("");
  const [takeProfit, setTakeProfit] = useState("");
  const [riskPct, setRiskPct] = useState("1");
  const [busy, setBusy] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmMode, setConfirmMode] = useState<"oneclick" | "ticket">("ticket");
  const [lastCheck, setLastCheck] = useState<Record<string, unknown> | null>(null);
  const [calc, setCalc] = useState<Record<string, unknown> | null>(null);
  const [validation, setValidation] = useState<Record<string, unknown> | null>(null);

  const accountQ = useQuery({
    queryKey: ["mt5-account"],
    queryFn: mt5Api.account,
    retry: false,
    enabled: connected,
  });
  const equity = num(asRecord(accountQ.data).equity);

  const mid =
    Number.isFinite(bid) && Number.isFinite(ask) && bid != null && ask != null
      ? (bid + ask) / 2
      : NaN;
  const spread =
    Number.isFinite(bid) && Number.isFinite(ask) && bid != null && ask != null
      ? ask - bid
      : NaN;

  const needsPrice = orderType !== "market";

  const buildPayload = () => ({
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
    comment: "quantforg-execution",
  });

  const refreshEstimates = async () => {
    if (!connected || !symbol) return;
    try {
      const payload = buildPayload();
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
    }, 400);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connected, symbol, side, orderType, volume, price, stopLoss, takeProfit]);

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
        toast.error("Order validation failed", {
          description: asRecord(v).messages
            ? String((asRecord(v).messages as unknown[])?.[0] ?? "Invalid")
            : "Invalid",
        });
        return;
      }
      const risk = await riskApi.check({
        request_id: payload.request_id,
        symbol: payload.symbol,
        side: payload.side,
        requested_lots: payload.volume,
        entry_price: payload.price || String(mid || 1),
        stop_loss_distance: stopLoss || undefined,
        equity: Number.isFinite(equity) ? String(equity) : undefined,
      });
      const check = await executionApi.check(payload);
      setLastCheck(asRecord(check));
      toast.success(`Safety: ${str(asRecord(check).decision)}`);
      if (asListish(asRecord(risk).warnings).length) {
        toast.message("Risk warnings", {
          description: asListish(asRecord(risk).warnings).slice(0, 2).join(" · "),
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
    try {
      const payload = {
        ...buildPayload(),
        side: confirmMode === "oneclick" ? side : side,
        order_type: confirmMode === "oneclick" ? "market" : orderType,
      };
      await mt5Api.validateOrder(payload);
      const check = await executionApi.check(payload);
      setLastCheck(asRecord(check));
      if (str(asRecord(check).decision) === "reject") {
        toast.error("Execution rejected", {
          description: asListish(asRecord(check).rejection_reasons).join(" · ") || "Rejected",
        });
        return;
      }
      const result = await executionApi.submit(payload);
      const outcome = str(asRecord(result).outcome);
      if (outcome === "disabled") {
        toast.message("Live send disabled", {
          description: str(asRecord(result).message, "EXECUTION_ENABLED is false on the server."),
        });
      } else if (outcome === "success") {
        toast.success("Order submitted", {
          description: `Ticket ${str(asRecord(result).order_ticket)}`,
        });
      } else if (asRecord(result).retryable) {
        toast.error(str(asRecord(result).message, outcome), {
          description: "Retryable — try again.",
        });
      } else {
        toast.error(str(asRecord(result).message, outcome));
      }
      setConfirmOpen(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Submit failed");
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
      <CardContent className={cn("space-y-4", dense && "space-y-3 px-3 pb-3")}>
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

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="exec-symbol">Symbol</Label>
            <Input
              id="exec-symbol"
              value={symbol}
              onChange={(e) => onSymbolChange(e.target.value.toUpperCase())}
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
            <Label htmlFor="exec-volume">Volume</Label>
            <div className="flex flex-wrap gap-1.5">
              {VOLUMES.map((v) => (
                <Button
                  key={v}
                  type="button"
                  size="sm"
                  variant={volume === v ? "default" : "secondary"}
                  onClick={() => setVolume(v)}
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
              onChange={(e) => setVolume(e.target.value)}
              disabled={!connected}
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
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="exec-risk">Risk per trade (%)</Label>
            <Input
              id="exec-risk"
              value={riskPct}
              onChange={(e) => setRiskPct(e.target.value)}
              disabled={!connected}
            />
            <p className="text-xs text-[var(--fg-subtle)]">
              Risk budget ≈ {positionSizeHint()} of equity {Number.isFinite(equity) ? formatCurrency(equity) : "—"}
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
