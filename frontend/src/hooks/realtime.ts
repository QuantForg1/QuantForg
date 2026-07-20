"use client";

import { useEffect } from "react";
import { useRealtimeContext } from "@/providers/realtime-provider";
import type {
  ChannelSubscriptionOptions,
  RealtimeChannel,
  RealtimeStatus,
} from "@/lib/realtime/types";

/** Core realtime status + manual subscribe helper. */
export function useRealtime(): RealtimeStatus & {
  subscribe: (
    channel: RealtimeChannel,
    opts?: ChannelSubscriptionOptions,
  ) => () => void;
} {
  const { status, subscribe } = useRealtimeContext();
  return { ...status, subscribe };
}

function useChannel(
  channel: RealtimeChannel,
  opts?: ChannelSubscriptionOptions,
  enabled = true,
) {
  const { subscribe, status } = useRealtimeContext();
  useEffect(() => {
    if (!enabled) return;
    return subscribe(channel, opts);
    // Intentionally depend on primitive option fields to avoid resubscribe thrash.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subscribe, channel, enabled, opts?.symbol, opts?.intervalMs]);
  return status;
}

export function usePortfolioStream(enabled = true) {
  return useChannel("portfolio", undefined, enabled);
}

export function useOrdersStream(enabled = true) {
  return useChannel("orders", undefined, enabled);
}

export function usePositionsStream(enabled = true) {
  return useChannel("positions", undefined, enabled);
}

export function useNotificationsStream(enabled = true) {
  return useChannel("notifications", undefined, enabled);
}

export function useMarketStream(symbol?: string, enabled = true) {
  const status = useChannel("market", undefined, enabled);
  useChannel("tick", { symbol }, enabled && Boolean(symbol));
  useChannel("mt5-status", undefined, enabled);
  return status;
}

export function useActivityStream(enabled = true) {
  return useChannel("activity", undefined, enabled);
}

export function useBrokerStatusStream(enabled = true) {
  useChannel("mt5-status", undefined, enabled);
  useChannel("weltrade-health", undefined, enabled);
  useChannel("brokers", undefined, enabled);
  useChannel("health", undefined, enabled);
  return useRealtimeContext().status;
}

/**
 * Live MT5 book sync — positions, orders, portfolio, history.
 * Keeps Open Positions / Recent Trades aligned with the terminal without a page refresh.
 */
export function useBookStream(enabled = true) {
  usePositionsStream(enabled);
  useOrdersStream(enabled);
  usePortfolioStream(enabled);
  useChannel("history", undefined, enabled);
  return useRealtimeContext().status;
}

export function useDashboardStream(enabled = true) {
  useBookStream(enabled);
  useNotificationsStream(enabled);
  useActivityStream(enabled);
  useBrokerStatusStream(enabled);
  useChannel("market", undefined, enabled);
  return useRealtimeContext().status;
}

export function useExecutionStream(symbol?: string, enabled = true) {
  useMarketStream(symbol, enabled);
  useBookStream(enabled);
  return useRealtimeContext().status;
}
