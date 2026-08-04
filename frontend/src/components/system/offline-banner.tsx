"use client";

import { useEffect, useState } from "react";
import { env } from "@/lib/env";
import {
  getApiConnectionState,
  markApiReachable,
  noteApiNetworkFailure,
  noteApiSlow,
  noteApiTimeout,
  subscribeApiConnection,
  type ApiConnectionState,
} from "@/lib/api/connectivity";
import { ApiError } from "@/lib/api/client";
import { platformApi } from "@/lib/api/endpoints";

/**
 * Browser offline + confirmed API unreachable.
 * Degraded (slow/timeout under load) does NOT show the red unreachable strip —
 * that was the false "API offline" bug when heavy MT5 routes timed out.
 */
export function OfflineBanner() {
  const [browserOffline, setBrowserOffline] = useState(false);
  const [apiState, setApiState] = useState<ApiConnectionState>(() =>
    getApiConnectionState(),
  );

  useEffect(() => {
    const sync = () => setBrowserOffline(!navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);

  useEffect(() => subscribeApiConnection(setApiState), []);

  // Independent lightweight health probe — clears false offline when backend recovers.
  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      if (cancelled || !navigator.onLine) return;
      try {
        await platformApi.health();
        if (!cancelled) markApiReachable();
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.code === "timeout") noteApiSlow();
        else noteApiNetworkFailure();
      }
    };
    void probe();
    const id = window.setInterval(probe, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const apiUnreachable = apiState === "unreachable";
  const apiDegraded = apiState === "degraded";

  if (!browserOffline && !apiUnreachable && !apiDegraded) return null;

  if (browserOffline) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="bg-[var(--warning)] px-4 py-2 text-center text-sm font-medium text-[var(--accent-fg)]"
      >
        You are offline. Cached views may be stale until connectivity returns.
      </div>
    );
  }

  if (apiUnreachable) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="bg-[var(--warning)] px-4 py-2 text-center text-sm font-medium text-[var(--accent-fg)]"
      >
        {env.apiBaseIsLocalFallback
          ? "API unreachable at local fallback (127.0.0.1:8000). Start the API or set NEXT_PUBLIC_API_BASE_URL."
          : "QuantForg API unreachable. Trading and sync pause until the backend responds."}
      </div>
    );
  }

  // Degraded: soft notice — backend may be busy (ITE/gateway), not dead.
  return (
    <div
      role="status"
      aria-live="polite"
      className="border-b border-[var(--border)] bg-[var(--surface)] px-4 py-1.5 text-center text-xs text-[var(--fg-muted)]"
    >
      API latency elevated. Backend may be busy — broker and gateway status are independent.
    </div>
  );
}
