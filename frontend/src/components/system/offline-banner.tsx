"use client";

import { useEffect, useState } from "react";
import { env } from "@/lib/env";
import {
  getApiConnectionState,
  markApiReachable,
  noteApiNetworkFailure,
  noteApiSlow,
  subscribeApiConnection,
  type ApiConnectionState,
} from "@/lib/api/connectivity";
import { ApiError } from "@/lib/api/client";
import { platformApi } from "@/lib/api/endpoints";

type OfflineBannerProps = {
  /**
   * Admin / ops shells may show confirmed API unreachable diagnostics.
   * Customer shells only surface browser-offline — never raw infrastructure banners.
   */
  showApiDiagnostics?: boolean;
};

/**
 * Connectivity chrome.
 * - Customer UI: browser offline only (no "API unreachable" strip).
 * - Admin UI: optional confirmed unreachable diagnostics (never degraded/slow).
 */
export function OfflineBanner({ showApiDiagnostics = false }: OfflineBannerProps) {
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

  useEffect(() => {
    let cancelled = false;
    const probe = async () => {
      if (cancelled || !navigator.onLine) return;
      try {
        await platformApi.healthLive();
        if (!cancelled) markApiReachable();
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.code === "timeout") noteApiSlow();
        else if (e instanceof ApiError && e.status > 0) {
          markApiReachable();
        } else noteApiNetworkFailure();
      }
    };
    void probe();
    const id = window.setInterval(probe, 30_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

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

  if (!showApiDiagnostics || apiState !== "unreachable") return null;

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
