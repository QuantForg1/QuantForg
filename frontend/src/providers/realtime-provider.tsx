"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { realtimeEngine } from "@/lib/realtime/engine";
import type {
  ChannelSubscriptionOptions,
  RealtimeChannel,
  RealtimeStatus,
} from "@/lib/realtime/types";
import { useAuth } from "@/providers/auth-provider";

type RealtimeContextValue = {
  status: RealtimeStatus;
  subscribe: (
    channel: RealtimeChannel,
    opts?: ChannelSubscriptionOptions,
  ) => () => void;
};

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

const INITIAL: RealtimeStatus = {
  transport: "polling",
  connected: false,
  online: true,
  visible: true,
  isLeader: true,
  latencyMs: null,
  lastHeartbeatAt: null,
  lastError: null,
  updatedAt: null,
  activeChannels: [],
};

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { isAuthenticated, loading } = useAuth();
  const [status, setStatus] = useState<RealtimeStatus>(INITIAL);

  useEffect(() => {
    if (loading || !isAuthenticated) {
      realtimeEngine.stop();
      setStatus(INITIAL);
      return;
    }
    realtimeEngine.start(queryClient);
    return realtimeEngine.onStatus(setStatus);
  }, [queryClient, isAuthenticated, loading]);

  useEffect(() => {
    return () => {
      realtimeEngine.stop();
    };
  }, []);

  const subscribe = useCallback(
    (channel: RealtimeChannel, opts?: ChannelSubscriptionOptions) => {
      if (!isAuthenticated) return () => undefined;
      return realtimeEngine.subscribe(channel, opts);
    },
    [isAuthenticated],
  );

  const value = useMemo<RealtimeContextValue>(
    () => ({ status, subscribe }),
    [status, subscribe],
  );

  return (
    <RealtimeContext.Provider value={value}>
      {children}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {!isAuthenticated
          ? "Realtime idle."
          : status.connected
            ? `Realtime ${status.transport}. Latency ${status.latencyMs ?? "—"} milliseconds.`
            : "Realtime offline."}
      </div>
    </RealtimeContext.Provider>
  );
}

export function useRealtimeContext(): RealtimeContextValue {
  const ctx = useContext(RealtimeContext);
  if (!ctx) {
    throw new Error("useRealtime hooks require RealtimeProvider");
  }
  return ctx;
}
