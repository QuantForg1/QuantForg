/**
 * Classify protected Mission Control / Journal / ITE audit query failures.
 * Never surface the raw backend "Missing bearer access token" string.
 */

import type { AuthPhase } from "./bootstrap";

export type ProtectedFailureKind =
  | "AUTH_BOOTSTRAP_PENDING"
  | "AUTH_REQUIRED"
  | "AUTH_EXPIRED"
  | "FORBIDDEN"
  | "NETWORK_ERROR"
  | "SERVER_ERROR"
  | "OK";

export function resolveBearerAuthorization(input: {
  auth: boolean;
  explicitToken?: string | null;
  storedToken: string | null;
}): { header: string | null; rejectCode: "auth_bootstrap_pending" | null } {
  if (!input.auth) {
    return { header: null, rejectCode: null };
  }
  const raw =
    input.explicitToken === undefined ? input.storedToken : input.explicitToken;
  const bearer = typeof raw === "string" ? raw.trim() : "";
  if (!bearer) {
    return { header: null, rejectCode: "auth_bootstrap_pending" };
  }
  return { header: `Bearer ${bearer}`, rejectCode: null };
}

function apiFailure(error: unknown): { status: number; code?: string } | null {
  if (!error || typeof error !== "object") return null;
  if (!("status" in error)) return null;
  const status = Number((error as { status?: unknown }).status);
  if (!Number.isFinite(status)) return null;
  const code =
    "code" in error && typeof (error as { code?: unknown }).code === "string"
      ? (error as { code: string }).code
      : undefined;
  return { status, code };
}

export function classifyProtectedFailure(input: {
  authPhase: AuthPhase;
  opsReady: boolean;
  error: unknown;
}): ProtectedFailureKind {
  if (!input.opsReady) {
    if (input.authPhase === "AUTH_LOADING") return "AUTH_BOOTSTRAP_PENDING";
    if (input.authPhase === "AUTH_REQUIRED") return "AUTH_REQUIRED";
    if (input.authPhase === "AUTH_TIMEOUT") return "AUTH_BOOTSTRAP_PENDING";
  }
  const api = apiFailure(input.error);
  if (!input.error) return "OK";
  if (api?.code === "auth_bootstrap_pending") return "AUTH_BOOTSTRAP_PENDING";
  if (api?.code === "missing_token") return "AUTH_REQUIRED";
  if (
    api?.status === 401 ||
    api?.code === "unauthorized" ||
    api?.code === "authentication_failed" ||
    api?.code === "invalid_token"
  ) {
    return "AUTH_EXPIRED";
  }
  if (api?.status === 403 || api?.code === "insufficient_role") return "FORBIDDEN";
  if (api?.code === "network_error" || api?.status === 0) return "NETWORK_ERROR";
  if (
    api?.code === "timeout" ||
    api?.status === 408 ||
    (api != null && api.status >= 500)
  ) {
    return "SERVER_ERROR";
  }
  return "SERVER_ERROR";
}

export function protectedFailureCopy(
  kind: ProtectedFailureKind,
  surface = "Timeline",
): { title: string; detail: string } {
  if (kind === "AUTH_BOOTSTRAP_PENDING") {
    return { title: "Authenticating…", detail: "Restoring session before loading protected feeds." };
  }
  if (kind === "AUTH_REQUIRED") {
    return { title: "Sign in required", detail: `${surface} needs an authenticated session.` };
  }
  if (kind === "AUTH_EXPIRED") {
    return {
      title: "Session expired — sign in again",
      detail: `${surface} could not use the current session.`,
    };
  }
  if (kind === "FORBIDDEN") {
    return {
      title: "You do not have permission",
      detail: `${surface} is limited to OWNER/ADMIN operators.`,
    };
  }
  if (kind === "NETWORK_ERROR" || kind === "SERVER_ERROR") {
    return {
      title: `${surface} temporarily unavailable`,
      detail: "This is not a Gateway, Broker, or MT5 disconnect.",
    };
  }
  return { title: surface, detail: "" };
}

export function copyContainsSecretLeak(text: string): boolean {
  return (
    /authorization:\s*bearer\s+\S+/i.test(text) ||
    /eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\./.test(text)
  );
}
