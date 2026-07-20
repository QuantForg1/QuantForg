"use client";

/**
 * Backward-compatible OrderTicket used by any legacy imports.
 * Delegates to the institutional ExecutionOrderTicket.
 */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExecutionOrderTicket } from "@/components/execution/order-ticket";
import { useExecutionStream } from "@/hooks/realtime";
import { mt5Api } from "@/lib/api/endpoints";
import { asRecord, num } from "@/lib/desk";
import { TRADING_SYMBOL, resolveTradingSymbol } from "@/lib/trading/gold-only";

export function OrderTicket() {
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  useExecutionStream(symbol);
  const status = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
  });
  const tick = useQuery({
    queryKey: ["mt5-tick", symbol],
    queryFn: () => mt5Api.tick(symbol),
    retry: false,
    enabled: Boolean(status.data?.connected),
  });
  const t = asRecord(tick.data);

  return (
    <ExecutionOrderTicket
      symbol={symbol}
      onSymbolChange={(s) => setSymbol(resolveTradingSymbol(s))}
      connected={Boolean(status.data?.connected)}
      bid={Number.isFinite(num(t.bid)) ? num(t.bid) : undefined}
      ask={Number.isFinite(num(t.ask)) ? num(t.ask) : undefined}
    />
  );
}
