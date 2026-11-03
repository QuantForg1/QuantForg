"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExecutionOrderTicket } from "@/components/execution/order-ticket";
import { useExecutionStream } from "@/hooks/realtime";
import { mt5Api } from "@/lib/api/endpoints";
import { asRecord, num } from "@/lib/desk";
import {
  displayTradingSymbol,
  resolveTradingSymbol,
  TRADING_SYMBOL,
} from "@/lib/trading/gold-only";

/**
 * Overview Trade panel — chrome matching the institutional dashboard reference.
 * Execution always goes through ExecutionOrderTicket (existing risk / OMS / confirm flow).
 */
export function OverviewTradePanel({ connected }: { connected: boolean }) {
  const [symbol, setSymbol] = useState(TRADING_SYMBOL);
  useExecutionStream(symbol);
  const tick = useQuery({
    queryKey: ["mt5-tick", symbol],
    queryFn: () => mt5Api.tick(symbol),
    retry: false,
    enabled: connected && Boolean(symbol),
    refetchInterval: connected ? 5_000 : false,
    staleTime: 2_000,
  });
  const t = asRecord(tick.data);
  const bid = num(t.bid);
  const ask = num(t.ask);
  const tickMsRaw = num(t.time_msc, NaN);
  const tickTimeMs = Number.isFinite(tickMsRaw)
    ? tickMsRaw > 1e12
      ? tickMsRaw
      : tickMsRaw * 1000
    : null;
  const marketOpen =
    typeof t.market_open === "boolean"
      ? t.market_open
      : typeof t.is_market_open === "boolean"
        ? t.is_market_open
        : null;

  return (
    <section
      aria-label={`Trade ${displayTradingSymbol(TRADING_SYMBOL)}`}
      className="overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] shadow-[var(--shadow-card)] backdrop-blur-[8px]"
    >
      <div className="flex flex-wrap items-end justify-between gap-2 border-b border-[var(--border)] px-4 py-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight text-[var(--fg)]">
            Trade {displayTradingSymbol(TRADING_SYMBOL)}
          </h2>
          <p className="mt-0.5 text-xs text-[var(--fg-muted)]">
            Execute trades with precision through the existing risk-checked order flow.
          </p>
        </div>
      </div>
      <ExecutionOrderTicket
        symbol={symbol}
        onSymbolChange={(s) => setSymbol(resolveTradingSymbol(s))}
        connected={connected}
        bid={Number.isFinite(bid) ? bid : undefined}
        ask={Number.isFinite(ask) ? ask : undefined}
        tickTimeMs={tickTimeMs}
        marketOpen={marketOpen}
        symbolAvailable={connected}
        embedded
      />
    </section>
  );
}
