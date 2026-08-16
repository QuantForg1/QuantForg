/**
 * Professional Connect MT5 action — never starts a second Gateway.
 * Browser never talks to 127.0.0.1:8765; all paths go through Railway API.
 */
import { weltradeApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asRecord } from "@/lib/desk";

export type ConnectMt5Result =
  | { outcome: "already_connected" }
  | { outcome: "not_configured"; href: "/broker" }
  | { outcome: "reconnected"; data: Record<string, unknown> }
  | { outcome: "gateway_unavailable"; message: string }
  | { outcome: "auth_failed"; message: string }
  | { outcome: "error"; message: string };

let inflight: Promise<ConnectMt5Result> | null = null;

export async function connectMt5Action(options?: {
  connected?: boolean;
}): Promise<ConnectMt5Result> {
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      if (options?.connected) {
        return { outcome: "already_connected" };
      }
      let profile: Record<string, unknown> | null = null;
      try {
        const meta = await weltradeApi.runtimeProfile();
        profile = asRecord(meta.profile);
        if (!profile.login) profile = null;
      } catch {
        profile = null;
      }
      if (!profile) {
        return { outcome: "not_configured", href: "/broker" };
      }
      try {
        const data = await weltradeApi.reconnect();
        return { outcome: "reconnected", data: asRecord(data) };
      } catch (first) {
        try {
          const data = await weltradeApi.restoreProfile();
          return { outcome: "reconnected", data: asRecord(data) };
        } catch (second) {
          const err = second instanceof ApiError ? second : first;
          const message =
            err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : "Reconnect failed";
          const lower = message.toLowerCase();
          if (
            lower.includes("auth") ||
            lower.includes("credential") ||
            lower.includes("password") ||
            lower.includes("login failed")
          ) {
            return { outcome: "auth_failed", message };
          }
          if (
            lower.includes("gateway") ||
            lower.includes("unavailable") ||
            (err instanceof ApiError && (err.status === 503 || err.status === 502))
          ) {
            return { outcome: "gateway_unavailable", message };
          }
          return { outcome: "error", message };
        }
      }
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}
