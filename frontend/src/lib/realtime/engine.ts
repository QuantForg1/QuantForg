import type { QueryClient } from "@tanstack/react-query";
import { createBackoff } from "@/lib/realtime/backoff";
import { getChannelDefinition } from "@/lib/realtime/channels";
import { createCrossTabBus, type CrossTabBus } from "@/lib/realtime/cross-tab";
import type {
  ChannelSubscriptionOptions,
  RealtimeChannel,
  RealtimeStatus,
  RealtimeTransport,
} from "@/lib/realtime/types";
import { env } from "@/lib/env";

type SubKey = string;

type ActiveSub = {
  channel: RealtimeChannel;
  opts?: ChannelSubscriptionOptions;
  refCount: number;
  timer: ReturnType<typeof setTimeout> | null;
  backoff: ReturnType<typeof createBackoff>;
  inFlight: boolean;
};

type StatusListener = (status: RealtimeStatus) => void;

function subKey(channel: RealtimeChannel, opts?: ChannelSubscriptionOptions): SubKey {
  if (channel === "tick") return `tick:${(opts?.symbol || "").toUpperCase()}`;
  return channel;
}

function wsCandidateUrls(): string[] {
  const http = env.apiBaseUrl.replace(/\/$/, "");
  const root = http.replace(/\/api\/v1$/, "");
  const toWs = (u: string) => u.replace(/^http/, "ws");
  return [`${toWs(root)}/ws`, `${toWs(http)}/ws`, `${toWs(root)}/api/v1/ws`];
}

/**
 * Shared realtime engine.
 * Probes for websocket endpoints; if none exist, uses efficient polling + cross-tab leadership.
 */
export class RealtimeEngine {
  private queryClient: QueryClient | null = null;
  private bus: CrossTabBus | null = null;
  private subs = new Map<SubKey, ActiveSub>();
  private statusListeners = new Set<StatusListener>();
  private transport: RealtimeTransport = "polling";
  private online = typeof navigator === "undefined" ? true : navigator.onLine;
  private visible = typeof document === "undefined" ? true : document.visibilityState === "visible";
  private isLeader = true;
  private latencyMs: number | null = null;
  private lastHeartbeatAt: number | null = null;
  private lastError: string | null = null;
  private updatedAt: number | null = null;
  private leaderTimer: ReturnType<typeof setInterval> | null = null;
  private lastLeaderSeen = 0;
  private started = false;
  private unsubscribers: Array<() => void> = [];

  start(queryClient: QueryClient) {
    if (this.started) {
      this.queryClient = queryClient;
      return;
    }
    this.started = true;
    this.queryClient = queryClient;
    this.bus = createCrossTabBus();

    const onOnline = () => {
      this.online = true;
      this.emitStatus();
      this.rescheduleAll();
    };
    const onOffline = () => {
      this.online = false;
      this.transport = "offline";
      this.emitStatus();
      this.clearAllTimers();
    };
    const onVisibility = () => {
      this.visible = document.visibilityState === "visible";
      this.emitStatus();
      this.rescheduleAll();
    };

    if (typeof window !== "undefined") {
      window.addEventListener("online", onOnline);
      window.addEventListener("offline", onOffline);
      document.addEventListener("visibilitychange", onVisibility);
      this.unsubscribers.push(() => {
        window.removeEventListener("online", onOnline);
        window.removeEventListener("offline", onOffline);
        document.removeEventListener("visibilitychange", onVisibility);
      });
    }

    this.unsubscribers.push(
      this.bus.subscribe((msg) => {
        if (msg.type === "leader-heartbeat" || msg.type === "leader-claim") {
          if (msg.tabId !== this.bus!.tabId) {
            this.lastLeaderSeen = msg.ts;
            if (msg.tabId < this.bus!.tabId) {
              this.isLeader = false;
              this.emitStatus();
            }
          }
        }
        if (msg.type === "query-data" && msg.tabId !== this.bus!.tabId && this.queryClient) {
          this.queryClient.setQueryData(msg.queryKey, msg.data);
          this.updatedAt = msg.updatedAt;
          this.emitStatus();
        }
      }),
    );

    this.leaderTimer = setInterval(() => this.tickLeadership(), 2_000);
    this.bus.post({
      type: "leader-claim",
      tabId: this.bus.tabId,
      ts: Date.now(),
    });
    void this.probeTransport();
    this.subscribe("heartbeat");
    this.emitStatus();
  }

  stop() {
    this.clearAllTimers();
    if (this.leaderTimer) clearInterval(this.leaderTimer);
    this.leaderTimer = null;
    for (const u of this.unsubscribers) u();
    this.unsubscribers = [];
    this.bus?.close();
    this.bus = null;
    this.subs.clear();
    this.started = false;
  }

  subscribe(channel: RealtimeChannel, opts?: ChannelSubscriptionOptions): () => void {
    const key = subKey(channel, opts);
    const existing = this.subs.get(key);
    if (existing) {
      existing.refCount += 1;
      if (opts?.intervalMs) {
        /* keep existing timer cadence */
      }
      return () => this.unsubscribe(key);
    }

    const def = getChannelDefinition(channel);
    if (!def) return () => undefined;

    const active: ActiveSub = {
      channel,
      opts,
      refCount: 1,
      timer: null,
      backoff: createBackoff(),
      inFlight: false,
    };
    this.subs.set(key, active);
    this.schedule(key, 0);
    this.emitStatus();
    return () => this.unsubscribe(key);
  }

  private unsubscribe(key: SubKey) {
    const sub = this.subs.get(key);
    if (!sub) return;
    sub.refCount -= 1;
    if (sub.refCount > 0) return;
    if (sub.timer) clearTimeout(sub.timer);
    this.subs.delete(key);
    this.emitStatus();
  }

  getStatus(): RealtimeStatus {
    return {
      transport: this.online ? this.transport : "offline",
      connected: this.online && this.transport !== "offline",
      online: this.online,
      visible: this.visible,
      isLeader: this.isLeader,
      latencyMs: this.latencyMs,
      lastHeartbeatAt: this.lastHeartbeatAt,
      lastError: this.lastError,
      updatedAt: this.updatedAt,
      activeChannels: [...new Set([...this.subs.values()].map((s) => s.channel))],
    };
  }

  onStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.getStatus());
    return () => this.statusListeners.delete(listener);
  }

  private emitStatus() {
    const status = this.getStatus();
    // Batch listener notifications to the next microtask to coalesce bursts.
    queueMicrotask(() => {
      for (const l of this.statusListeners) l(status);
    });
  }

  private tickLeadership() {
    if (!this.bus) return;
    const now = Date.now();
    if (this.isLeader) {
      this.bus.post({ type: "leader-heartbeat", tabId: this.bus.tabId, ts: now });
    } else if (now - this.lastLeaderSeen > 5_000) {
      this.isLeader = true;
      this.bus.post({ type: "leader-claim", tabId: this.bus.tabId, ts: now });
      this.emitStatus();
      this.rescheduleAll();
    }
  }

  private async probeTransport() {
    if (typeof window === "undefined") return;
    // Soft probe only — never invent socket events. Fallback remains polling.
    for (const url of wsCandidateUrls()) {
      const ok = await this.tryWebSocket(url, 1200);
      if (ok) {
        // Endpoint may exist later; we still don't receive a protocol schema.
        // Stay on polling to avoid fake/partial realtime frames.
        this.transport = "polling";
        this.lastError = null;
        this.emitStatus();
        return;
      }
    }
    this.transport = this.online ? "polling" : "offline";
    this.emitStatus();
  }

  private tryWebSocket(url: string, timeoutMs: number): Promise<boolean> {
    return new Promise((resolve) => {
      let settled = false;
      let ws: WebSocket;
      try {
        ws = new WebSocket(url);
      } catch {
        resolve(false);
        return;
      }
      const done = (value: boolean) => {
        if (settled) return;
        settled = true;
        try {
          ws.close();
        } catch {
          /* ignore */
        }
        resolve(value);
      };
      const timer = setTimeout(() => done(false), timeoutMs);
      ws.onopen = () => {
        clearTimeout(timer);
        // Open alone is insufficient without a documented protocol — treat as unavailable.
        done(false);
      };
      ws.onerror = () => {
        clearTimeout(timer);
        done(false);
      };
    });
  }

  private clearAllTimers() {
    for (const sub of this.subs.values()) {
      if (sub.timer) clearTimeout(sub.timer);
      sub.timer = null;
    }
  }

  private rescheduleAll() {
    for (const key of this.subs.keys()) {
      this.schedule(key, 0);
    }
  }

  private schedule(key: SubKey, delayMs: number) {
    const sub = this.subs.get(key);
    if (!sub) return;
    if (sub.timer) clearTimeout(sub.timer);
    sub.timer = setTimeout(() => {
      void this.poll(key);
    }, Math.max(0, delayMs));
  }

  private async poll(key: SubKey) {
    const sub = this.subs.get(key);
    if (!sub || !this.queryClient) return;
    const def = getChannelDefinition(sub.channel);
    if (!def) return;

    if (def.enabled && !def.enabled(sub.opts)) {
      this.schedule(key, def.intervalMs);
      return;
    }

    if (!this.online) {
      this.schedule(key, def.hiddenIntervalMs);
      return;
    }

    // Followers receive data via BroadcastChannel; still keep light heartbeat locally.
    if (!this.isLeader && sub.channel !== "heartbeat") {
      const base = this.visible ? def.intervalMs : def.hiddenIntervalMs;
      const override = sub.opts?.intervalMs;
      const delay = (override ?? base) * (this.visible ? 2 : 1);
      this.schedule(key, delay);
      return;
    }

    if (sub.inFlight) {
      this.schedule(key, 500);
      return;
    }

    sub.inFlight = true;
    const started = performance.now();
    try {
      const data = await def.fetcher(sub.opts);
      const elapsed = Math.round(performance.now() - started);
      const qk = def.queryKey(sub.opts);

      if (sub.channel === "heartbeat") {
        this.latencyMs = elapsed;
        this.lastHeartbeatAt = Date.now();
        this.transport = "polling";
        this.lastError = null;
      }

      this.queryClient.setQueryData(qk, data);
      this.updatedAt = Date.now();
      sub.backoff.reset();

      this.bus?.post({
        type: "query-data",
        tabId: this.bus.tabId,
        queryKey: qk,
        data,
        updatedAt: this.updatedAt,
        channel: sub.channel,
      });

      this.emitStatus();
      const base = this.visible ? def.intervalMs : def.hiddenIntervalMs;
      const override = sub.opts?.intervalMs;
      this.schedule(key, override ?? base);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Realtime poll failed";
      this.lastError = message;
      if (sub.channel === "heartbeat") {
        this.latencyMs = null;
      }
      this.emitStatus();
      this.schedule(key, sub.backoff.next());
    } finally {
      sub.inFlight = false;
    }
  }
}

export const realtimeEngine = new RealtimeEngine();
