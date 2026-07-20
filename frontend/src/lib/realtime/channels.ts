import { mt5Api, platformApi, portfolioApi, brokersApi, weltradeApi } from "@/lib/api/endpoints";
import type { ChannelDefinition, ChannelSubscriptionOptions } from "@/lib/realtime/types";

export const CHANNEL_DEFINITIONS: ChannelDefinition[] = [
  {
    channel: "heartbeat",
    queryKey: () => ["realtime-heartbeat"],
    fetcher: () => platformApi.healthLive(),
    intervalMs: 15_000,
    hiddenIntervalMs: 45_000,
    requiresAuth: false,
  },
  {
    channel: "health",
    queryKey: () => ["health"],
    fetcher: () => platformApi.health(),
    intervalMs: 30_000,
    hiddenIntervalMs: 90_000,
    requiresAuth: false,
  },
  {
    channel: "portfolio",
    queryKey: () => ["portfolio"],
    fetcher: () => portfolioApi.get(),
    intervalMs: 8_000,
    hiddenIntervalMs: 30_000,
    requiresAuth: true,
  },
  {
    channel: "orders",
    queryKey: () => ["orders"],
    fetcher: () => portfolioApi.orders(),
    intervalMs: 5_000,
    hiddenIntervalMs: 20_000,
    requiresAuth: true,
  },
  {
    channel: "positions",
    queryKey: () => ["positions"],
    fetcher: () => portfolioApi.positions(),
    intervalMs: 5_000,
    hiddenIntervalMs: 20_000,
    requiresAuth: true,
  },
  {
    channel: "history",
    queryKey: () => ["history"],
    fetcher: () => portfolioApi.history(),
    intervalMs: 10_000,
    hiddenIntervalMs: 30_000,
    requiresAuth: true,
  },
  {
    channel: "notifications",
    queryKey: () => ["notifications"],
    fetcher: () => platformApi.notifications(false),
    intervalMs: 20_000,
    hiddenIntervalMs: 60_000,
    requiresAuth: true,
  },
  {
    channel: "activity",
    queryKey: () => ["activity"],
    fetcher: () => platformApi.activity(),
    intervalMs: 30_000,
    hiddenIntervalMs: 90_000,
    requiresAuth: true,
  },
  {
    channel: "mt5-status",
    queryKey: () => ["mt5-status"],
    fetcher: () => mt5Api.status(),
    intervalMs: 15_000,
    hiddenIntervalMs: 60_000,
    requiresAuth: true,
  },
  {
    channel: "weltrade-health",
    queryKey: () => ["weltrade-health"],
    fetcher: () => weltradeApi.health(),
    intervalMs: 20_000,
    hiddenIntervalMs: 60_000,
    requiresAuth: true,
  },
  {
    channel: "market",
    queryKey: () => ["mt5-symbols", "", 0],
    fetcher: () => mt5Api.symbols({ limit: 80, offset: 0, include_quotes: false }),
    intervalMs: 60_000,
    hiddenIntervalMs: 180_000,
    requiresAuth: true,
  },
  {
    channel: "tick",
    /** Keep query key casing aligned with page hooks (symbol as selected). */
    queryKey: (opts?: ChannelSubscriptionOptions) => [
      "mt5-tick",
      opts?.symbol || "",
    ],
    fetcher: (opts?: ChannelSubscriptionOptions) => {
      const symbol = (opts?.symbol || "").trim();
      if (!symbol) return Promise.resolve(null);
      return mt5Api.tick(symbol.toUpperCase());
    },
    intervalMs: 3_000,
    hiddenIntervalMs: 20_000,
    requiresAuth: true,
    enabled: (opts) => Boolean(opts?.symbol?.trim()),
  },
  {
    channel: "brokers",
    queryKey: () => ["brokers"],
    fetcher: () => brokersApi.list(),
    intervalMs: 45_000,
    hiddenIntervalMs: 120_000,
    requiresAuth: true,
  },
];

export function getChannelDefinition(channel: string): ChannelDefinition | undefined {
  return CHANNEL_DEFINITIONS.find((c) => c.channel === channel);
}
