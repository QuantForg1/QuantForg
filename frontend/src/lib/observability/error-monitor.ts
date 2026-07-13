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

  const next = [event, ...load()].slice(0, MAX);
  persist(next);
  void maybeShip(event);

  if (process.env.NODE_ENV !== "production") {
    console.error("qf_monitored_error", {
      kind: event.kind,
      message: event.message,
      request_id: event.request_id,
      route: event.route,
    });
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
    captureError("unhandled_rejection", ev.reason);
  });
}
