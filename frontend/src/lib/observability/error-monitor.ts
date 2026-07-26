import {
  buildObservabilityContext,
  sanitizePayload,
  type ObservabilityContext,
} from "@/lib/observability/context";
import { getStoredUser } from "@/lib/auth/session";

export type MonitoredError = ObservabilityContext & {
  id: string;
  kind:
    | "runtime"
    | "react"
    | "api"
    | "execution"
    | "mt5"
    | "unhandled_rejection"
    | "route";
  message: string;
  stack?: string;
  status?: number;
  path?: string;
  details?: unknown;
};

const STORAGE_KEY = "qf.ops.errors.v1";
const MAX = 80;
const listeners = new Set<(events: MonitoredError[]) => void>();

function load(): MonitoredError[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MonitoredError[]) : [];
  } catch {
    return [];
  }
}

function persist(events: MonitoredError[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(0, MAX)));
  } catch {
    /* quota */
  }
  for (const l of listeners) l(events.slice(0, MAX));
}

async function maybeShip(event: MonitoredError) {
  const url = process.env.NEXT_PUBLIC_ERROR_WEBHOOK_URL?.trim();
  if (!url || typeof fetch === "undefined") return;
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(sanitizePayload(event)),
      keepalive: true,
    });
  } catch {
    /* never throw from monitoring */
  }
}

export function listMonitoredErrors(): MonitoredError[] {
  return load();
}

export function clearMonitoredErrors() {
  persist([]);
}

export function subscribeMonitoredErrors(fn: (events: MonitoredError[]) => void) {
  listeners.add(fn);
  fn(load());
  return () => listeners.delete(fn);
}

const recentLogAt = new Map<string, number>();

export function captureError(
  kind: MonitoredError["kind"],
  error: unknown,
  extra?: {
    request_id?: string;
    status?: number;
    path?: string;
    details?: unknown;
    user_id?: string | null;
  },
) {
  const user = getStoredUser();
  const message =
    error instanceof Error
      ? error.message
      : typeof error === "string"
        ? error
        : "Unknown error";
  const stack = error instanceof Error ? error.stack : undefined;
  const ctx = buildObservabilityContext({
    request_id: extra?.request_id,
    user_id: extra?.user_id ?? user?.id ?? null,
  });
  const event: MonitoredError = {
    ...ctx,
    id: `err_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    kind,
    message: message.slice(0, 500),
    stack: stack?.slice(0, 2000),
    status: extra?.status,
    path: extra?.path,
    details: sanitizePayload(extra?.details),
  };

  const isNetwork =
    extra?.status === 0 ||
    /failed to fetch|network_error|unable to reach the quantforg api/i.test(
      event.message,
    );

  // Deduplicate noisy network failures (same kind+path within window).
  const dedupeKey = `${event.kind}|${event.path || ""}|${isNetwork ? "net" : event.message}`;
  const now = Date.now();
  const last = recentLogAt.get(dedupeKey) ?? 0;
  const withinWindow = now - last < (isNetwork ? 30_000 : 5_000);
  if (!withinWindow) {
    recentLogAt.set(dedupeKey, now);
    if (recentLogAt.size > 200) {
      const oldest = recentLogAt.keys().next().value;
      if (oldest) recentLogAt.delete(oldest);
    }

    const next = [event, ...load()].slice(0, MAX);
    persist(next);
    void maybeShip(event);

    if (process.env.NODE_ENV !== "production") {
      if (isNetwork) {
        // One quiet warning — ConnectionBanner surfaces the operator-facing state.
        console.warn("qf_api_unreachable", {
          kind: event.kind,
          path: event.path,
          api: process.env.NEXT_PUBLIC_API_BASE_URL || "(dev fallback)",
        });
      } else {
        console.error("qf_monitored_error", {
          kind: event.kind,
          message: event.message,
          request_id: event.request_id,
          route: event.route,
        });
      }
    }
  }

  return event;
}

let installed = false;

/** Install global listeners once (browser only). */
export function installErrorMonitoring() {
  if (installed || typeof window === "undefined") return;
  installed = true;

  window.addEventListener("error", (ev) => {
    captureError("runtime", ev.error || ev.message, {
      details: { filename: ev.filename, lineno: ev.lineno, colno: ev.colno },
    });
  });

  window.addEventListener("unhandledrejection", (ev) => {
    const reason = ev.reason;
    const msg =
      reason instanceof Error
        ? reason.message
        : typeof reason === "string"
          ? reason
          : "";
    // Network failures are handled by apiFetch + ConnectionBanner — avoid double spam.
    if (
      /failed to fetch|network_error|unable to reach the quantforg api/i.test(msg)
    ) {
      return;
    }
    captureError("unhandled_rejection", reason);
  });
}
