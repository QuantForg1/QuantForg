"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { portfolioApi } from "@/lib/api/endpoints";
import { asList, asRecord, num } from "@/lib/desk";
import {
  attachStopsFromPositions,
  computeTradeAnalytics,
  pairDealsIntoTrades,
  parseLiveDeal,
  rangeToIso,
  type HistoryRange,
  type LiveTrade,
  type TradeAnalytics,
} from "@/lib/orders/history";
import { useTradingSession } from "@/providers/trading-session-provider";

/** Shared LIVE closed-trade feed for Operator OS (never fabricated). */
export function useLiveTrades(range: HistoryRange = "month") {
  const session = useTradingSession();
  const iso = rangeToIso(range);

  const historyQ = useQuery({
    queryKey: ["portfolio-history", "operator", range, iso.date_from, iso.date_to],
    queryFn: () => portfolioApi.historyRange(iso),
    staleTime: 20_000,
    refetchInterval: 45_000,
    retry: false,
    enabled: session.connected || session.gatewayOnline,
  });

  const trades = useMemo((): LiveTrade[] => {
    const deals = asList(
      asRecord(historyQ.data).deals ||
        asRecord(historyQ.data).items ||
        asRecord(historyQ.data).history ||
        historyQ.data,
    )
      .map(asRecord)
      .map(parseLiveDeal)
      .filter((d): d is NonNullable<typeof d> => Boolean(d));
    const paired = pairDealsIntoTrades(deals);
    const positions = session.positions.map((p) => {
      const r = asRecord(p);
      return {
        ticket: num(r.ticket),
        stop_loss: num(r.stop_loss ?? r.sl, 0) || undefined,
        take_profit: num(r.take_profit ?? r.tp, 0) || undefined,
      };
    });
    return attachStopsFromPositions(paired, positions);
  }, [historyQ.data, session.positions]);

  const analytics = useMemo((): TradeAnalytics => {
    const equity = num(session.equity, 0);
    return computeTradeAnalytics(trades, { startingEquity: equity });
  }, [session.equity, trades]);

  return {
    trades,
    analytics,
    loading: historyQ.isLoading,
    error: historyQ.isError,
    refetch: historyQ.refetch,
    connected: session.connected,
    session,
  };
}
