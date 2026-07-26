"use client";

import { useEffect, useState } from "react";
import { env } from "@/lib/env";
import {
  getApiConnectionState,
  subscribeApiConnection,
  type ApiConnectionState,
} from "@/lib/api/connectivity";

/**
 * Single connection-state strip for browser offline + API unreachable.
 * Uses existing warning-banner chrome (Design Freeze — no new visual language).
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

  const apiUnreachable = apiState === "unreachable";
  if (!browserOffline && !apiUnreachable) return null;

  const message = browserOffline
    ? "You are offline. Cached views may be stale until connectivity returns."
    : env.apiBaseIsLocalFallback
      ? "API unreachable at local fallback (127.0.0.1:8000). Start the API or set NEXT_PUBLIC_API_BASE_URL."
      : "QuantForg API unreachable. Trading and sync pause until the backend responds.";

  return (
    <div
      role="status"
      aria-live="polite"
      className="bg-[var(--warning)] px-4 py-2 text-center text-sm font-medium text-black"
    >
      {message}
    </div>
  );
}
