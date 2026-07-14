export type RealtimeTransport = "polling" | "websocket" | "offline";

export type RealtimeChannel =
  | "heartbeat"
  | "portfolio"
  | "orders"
  | "positions"
  | "history"
  | "notifications"
  | "market"
  | "tick"
  | "mt5-status"
  | "weltrade-health"
  | "activity"
  | "health"
  | "brokers";

export type RealtimeStatus = {
  transport: RealtimeTransport;
  connected: boolean;
  online: boolean;
  visible: boolean;
  isLeader: boolean;
  latencyMs: number | null;
  lastHeartbeatAt: number | null;
  lastError: string | null;
  updatedAt: number | null;
  activeChannels: RealtimeChannel[];
};

export type ChannelSubscriptionOptions = {
  /** Required for `tick` channel */
  symbol?: string;
  /** Override poll interval (ms) */
  intervalMs?: number;
};

export type ChannelDefinition = {
  channel: RealtimeChannel;
  /** Build query key from options */
  queryKey: (opts?: ChannelSubscriptionOptions) => unknown[];
  fetcher: (opts?: ChannelSubscriptionOptions) => Promise<unknown>;
  intervalMs: number;
  hiddenIntervalMs: number;
  requiresAuth?: boolean;
  /** Skip fetch when predicate fails (e.g. no symbol) */
  enabled?: (opts?: ChannelSubscriptionOptions) => boolean;
};

export type CrossTabMessage =
  | { type: "leader-claim"; tabId: string; ts: number }
  | { type: "leader-heartbeat"; tabId: string; ts: number }
  | {
      type: "query-data";
      tabId: string;
      queryKey: unknown[];
      data: unknown;
      updatedAt: number;
      channel: RealtimeChannel;
    }
  | {
      type: "status";
      tabId: string;
      status: Partial<RealtimeStatus>;
    };
