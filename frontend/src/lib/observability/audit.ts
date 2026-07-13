import {
  buildObservabilityContext,
  sanitizePayload,
  type ObservabilityContext,
} from "@/lib/observability/context";
import { getStoredUser } from "@/lib/auth/session";

export type AuditAction =
  | "login"
  | "logout"
  | "register"
  | "password_reset"
  | "broker_connect"
  | "broker_disconnect"
  | "order_submit"
  | "order_cancel"
  | "position_close"
  | "settings_change"
  | "organization_change"
  | "feedback_submit"
  | "beta_unlock"
  | "feature_flag_override";

export type AuditEvent = ObservabilityContext & {
  id: string;
  action: AuditAction;
  outcome: "success" | "failure" | "info";
  summary: string;
  metadata?: unknown;
};

const STORAGE_KEY = "qf.ops.audit.v1";
const MAX = 120;
const listeners = new Set<(events: AuditEvent[]) => void>();

function load(): AuditEvent[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AuditEvent[]) : [];
  } catch {
    return [];
  }
}

function persist(events: AuditEvent[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(events.slice(0, MAX)));
  } catch {
    /* ignore */
  }
  for (const l of listeners) l(events.slice(0, MAX));
}

async function maybeShip(event: AuditEvent) {
  const url = process.env.NEXT_PUBLIC_AUDIT_WEBHOOK_URL?.trim();
  if (!url || typeof fetch === "undefined") return;
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(sanitizePayload(event)),
      keepalive: true,
    });
  } catch {
    /* ignore */
  }
}

export function listAuditEvents(): AuditEvent[] {
  return load();
}

export function clearAuditEvents() {
  persist([]);
}

export function subscribeAuditEvents(fn: (events: AuditEvent[]) => void) {
  listeners.add(fn);
  fn(load());
  return () => listeners.delete(fn);
}

export function recordAudit(
  action: AuditAction,
  outcome: AuditEvent["outcome"],
  summary: string,
  metadata?: unknown,
) {
  const user = getStoredUser();
  const ctx = buildObservabilityContext({ user_id: user?.id ?? null });
  const event: AuditEvent = {
    ...ctx,
    id: `aud_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    action,
    outcome,
    summary: summary.slice(0, 300),
    metadata: sanitizePayload(metadata),
  };
  persist([event, ...load()].slice(0, MAX));
  void maybeShip(event);
  return event;
}
