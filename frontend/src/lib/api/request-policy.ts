/**
 * Shared request policy for the authenticated API client.
 * Timeouts and GET dedupe live here so Auto Trading / auth bootstrap
 * cannot drift from the client implementation.
 */

/** Default hard timeout so UI never spins forever on a hung API. */
export const API_DEFAULT_TIMEOUT_MS = 25_000;
/** /auth/me, login, refresh — Railway cold-start budget. */
export const API_AUTH_TIMEOUT_MS = 40_000;
/** Public health probes — /health/live must fail fast, never wait on MT5. */
export const API_HEALTH_LIVE_TIMEOUT_MS = 4_000;
/** Other /health* probes (still lightweight on the server). */
export const API_HEALTH_TIMEOUT_MS = 8_000;
/** MT5 / Weltrade / ITE ops. */
export const API_HEAVY_TIMEOUT_MS = 45_000;

/** Last-resort AppShell cap after the first /auth/me attempt. */
export function sessionBootBudgetMs(
  authTimeoutMs = API_AUTH_TIMEOUT_MS,
  slackMs = 8_000,
): number {
  return authTimeoutMs + slackMs;
}

export function defaultTimeoutForPath(path: string): number {
  const p = path.startsWith("http") ? new URL(path).pathname : path;
  if (
    p.includes("/auth/login") ||
    p.includes("/auth/refresh") ||
    p.includes("/auth/me")
  ) {
    return API_AUTH_TIMEOUT_MS;
  }
  if (p.endsWith("/health/live") || p.includes("/health/live")) {
    return API_HEALTH_LIVE_TIMEOUT_MS;
  }
  if (p.endsWith("/health") || p.includes("/health/")) {
    return API_HEALTH_TIMEOUT_MS;
  }
  if (
    p.includes("/mt5") ||
    p.includes("/weltrade") ||
    p.includes("/signals") ||
    p.includes("/symbol") ||
    p.includes("/auto-trading") ||
    p.includes("/ite")
  ) {
    return API_HEAVY_TIMEOUT_MS;
  }
  return API_DEFAULT_TIMEOUT_MS;
}

/** Identical in-flight GETs share one promise on first load. */
export function shouldDedupeGet(path: string): boolean {
  const p = path.startsWith("http") ? new URL(path).pathname : path;
  return (
    p.includes("/health") ||
    p.includes("/weltrade/health") ||
    p.includes("/mt5/status") ||
    p.includes("/mt5/symbols") ||
    p.includes("/auth/me") ||
    p.includes("/ite/ops/auto-trading") ||
    p.includes("/ite/ops/control-center") ||
    p.includes("/ite/ops/launch-readiness") ||
    p.includes("/trading-components") ||
    p.endsWith("/portfolio") ||
    p.endsWith("/positions") ||
    p.endsWith("/orders") ||
    p.endsWith("/history")
  );
}

/** One refresh + one retry. Never loop. */
export function shouldAttemptTokenRefresh(args: {
  status: number;
  authEnabled: boolean;
  alreadyRetried: boolean;
}): boolean {
  return args.status === 401 && args.authEnabled && !args.alreadyRetried;
}

export function isTimeoutFailure(error: {
  status?: number;
  code?: string;
} | null | undefined): boolean {
  if (!error) return false;
  return error.code === "timeout" || error.status === 408;
}

export function isUnauthorizedFailure(error: {
  status?: number;
  code?: string;
} | null | undefined): boolean {
  if (!error) return false;
  return (
    error.status === 401 ||
    error.code === "unauthorized" ||
    error.code === "missing_token" ||
    error.code === "authentication_failed"
  );
}
