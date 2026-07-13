import type { CrossTabMessage } from "@/lib/realtime/types";

const CHANNEL_NAME = "quantforg-realtime-v1";

export type CrossTabBus = {
  tabId: string;
  post: (msg: CrossTabMessage) => void;
  subscribe: (fn: (msg: CrossTabMessage) => void) => () => void;
  close: () => void;
};

export function createCrossTabBus(): CrossTabBus {
  const tabId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `tab_${Date.now()}_${Math.random().toString(36).slice(2)}`;

  let channel: BroadcastChannel | null = null;
  const listeners = new Set<(msg: CrossTabMessage) => void>();

  if (typeof BroadcastChannel !== "undefined") {
    channel = new BroadcastChannel(CHANNEL_NAME);
    channel.onmessage = (event: MessageEvent<CrossTabMessage>) => {
      const data = event.data;
      if (!data || typeof data !== "object") return;
      for (const fn of listeners) fn(data);
    };
  }

  return {
    tabId,
    post(msg) {
      try {
        channel?.postMessage(msg);
      } catch {
        /* ignore structured clone failures */
      }
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    close() {
      listeners.clear();
      channel?.close();
      channel = null;
    },
  };
}
