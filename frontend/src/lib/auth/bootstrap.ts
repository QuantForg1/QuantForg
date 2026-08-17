/**
 * Auth bootstrap phases — keep protected ops behind AUTH READY.
 *
 * APP LOAD → RESTORE TOKEN → /auth/me → AUTH READY → authenticated client
 * Stale stored user must not mark isAuthenticated while /auth/me is in flight.
 */

export type AuthPhase =
  | "AUTH_LOADING"
  | "AUTH_READY"
  | "AUTH_TIMEOUT"
  | "AUTH_REQUIRED";

export type MeAttemptStatus =
  | "idle"
  | "success"
  | "timeout"
  | "unauthorized"
  | "error";

export function resolveAuthPhase(input: {
  loading: boolean;
  hasToken: boolean;
  hasUser: boolean;
  meStatus: MeAttemptStatus;
}): AuthPhase {
  if (input.meStatus === "unauthorized") return "AUTH_REQUIRED";
  if (input.loading || input.meStatus === "idle") return "AUTH_LOADING";
  if (input.meStatus === "success" && input.hasUser) return "AUTH_READY";
  if (input.meStatus === "timeout") {
    return input.hasToken && input.hasUser ? "AUTH_TIMEOUT" : "AUTH_REQUIRED";
  }
  if (input.meStatus === "error") {
    return input.hasToken && input.hasUser ? "AUTH_TIMEOUT" : "AUTH_REQUIRED";
  }
  if (!input.hasToken) return "AUTH_REQUIRED";
  return "AUTH_LOADING";
}

/** Protected ITE/ops calls wait until /auth/me settled (ready or timeout-with-token). */
export function canIssueProtectedOps(phase: AuthPhase, hasToken: boolean): boolean {
  if (!hasToken) return false;
  return phase === "AUTH_READY" || phase === "AUTH_TIMEOUT";
}

export function isAuthenticatedPhase(phase: AuthPhase, hasUser: boolean): boolean {
  if (!hasUser) return false;
  return phase === "AUTH_READY" || phase === "AUTH_TIMEOUT";
}

export function authBootBanner(phase: AuthPhase): string | null {
  if (phase === "AUTH_TIMEOUT") {
    return "Session check delayed. Retry if the desk looks stale — you are still signed in.";
  }
  if (phase === "AUTH_REQUIRED") {
    return "Sign in required.";
  }
  return null;
}
