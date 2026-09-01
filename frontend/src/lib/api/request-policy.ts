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
/** MT5 / Weltrade / ITE ops / book snapshot. */
export const API_HEAVY_TIMEOUT_MS = 45_000;
/** Dashboard / audit / observability — fail fast, never block a decision. */
export const API_TELEMETRY_TIMEOUT_MS = 8_000;

/** Last-resort AppShell cap after the first /auth/me attempt. */
export function sessionBootBudgetMs(
  authTimeoutMs = API_AUTH_TIMEOUT_MS,
  slackMs = 8_000,
): number {
  return authTimeoutMs + slackMs;
}

export function requestPathname(path: string): string {
  const raw = path.startsWith("http")
    ? new URL(path).pathname
    : path.split("?")[0] || path;
  return raw.replace(/\/$/, "") || "/";
}

export function isTelemetryPath(path: string): boolean {
  const p = requestPathname(path);
  return (
    p.includes("/institutional-observability") ||
    p.includes("/execution/journal") ||
    p.includes("/execution/analytics") ||
    p.includes("/execution/audits") ||
    p.includes("/execution/optimization") ||
    p.includes("/ite/ops/audit") ||
    p.includes("/ite/ops/services-health") ||
    p.includes("/ite/ops/live-evidence") ||
    p.includes("/mission-control/dashboard") ||
    p.endsWith("/history")
  );
}

export function isCriticalTradingPath(path: string): boolean {
  const p = requestPathname(path);
  return (
    p.includes("/mt5/ticks") ||
    p.includes("/mt5/account") ||
    p.includes("/mt5/status") ||
    p.includes("/mt5/order") ||
    p.includes("/positions") ||
    p.endsWith("/orders") ||
    (p.endsWith("/portfolio") &&
      !p.includes("intelligence") &&
      !p.includes("analytics") &&
      !p.includes("/strategy/")) ||
    p.includes("/strategy/evaluate") ||
    p.includes("/ite/ops/auto-trading") ||
    p.includes("/ite/ops/status") ||
    p.includes("/execution/submit") ||
    p.includes("/execution/check") ||
    p.includes("/weltrade/health")
  );
}

export function defaultTimeoutForPath(path: string): number {
  const p = requestPathname(path);
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
  if (p.includes("/health/trading-components")) {
    return API_HEAVY_TIMEOUT_MS;
  }
  // Public /health and /health/ready only — never /weltrade/health.
  if (
    p.endsWith("/health") &&
    !p.includes("/weltrade") &&
    !p.includes("/institutional-observability")
  ) {
    return API_HEALTH_TIMEOUT_MS;
  }
  if (p.includes("/health/") && !p.includes("/weltrade")) {
    return API_HEALTH_TIMEOUT_MS;
  }
  if (isTelemetryPath(p)) {
    return API_TELEMETRY_TIMEOUT_MS;
  }
  if (
    p.includes("/mt5") ||
    p.includes("/weltrade") ||
    p.includes("/ite") ||
    p.includes("/auto-trading") ||
    p.includes("/positions") ||
    p.endsWith("/orders") ||
    (p.endsWith("/portfolio") && !p.includes("intelligence")) ||
    p.includes("/execution/submit") ||
    p.includes("/execution/check") ||
    p.includes("/execution/cancel") ||
    p.includes("/signals") ||
    p.includes("/symbol")
  ) {
    return API_HEAVY_TIMEOUT_MS;
  }
  return API_DEFAULT_TIMEOUT_MS;
}

/** Identical in-flight GETs share one promise on first load. */
export function shouldDedupeGet(path: string): boolean {
  const p = requestPathname(path);
  return (
    p.includes("/health") ||
    p.includes("/weltrade/health") ||
    p.includes("/mt5/status") ||
    p.includes("/mt5/account") ||
    p.includes("/mt5/ticks") ||
    p.includes("/mt5/symbols") ||
    p.includes("/auth/me") ||
    p.includes("/ite/ops/auto-trading") ||
    p.includes("/ite/ops/control-center") ||
    p.includes("/ite/ops/launch-readiness") ||
    p.includes("/ite/ops/audit") ||
    p.includes("/ite/ops/status") ||
    p.includes("/execution/journal") ||
    p.includes("/execution/analytics") ||
    p.includes("/execution/audits") ||
    p.includes("/institutional-observability") ||
    p.includes("/mission-control") ||
    p.includes("/trading-components") ||
    p.endsWith("/portfolio") ||
    p.endsWith("/positions") ||
    p.includes("/positions") ||
    p.endsWith("/orders") ||
    p.endsWith("/history") ||
    p.endsWith("/brokers") ||
    p.endsWith("/trading/session") ||
    p.endsWith("/trading/account")
  );
}

/** Terminal pre-trade calculate is read-only — coalesce identical in-flight POSTs. */
export function shouldDedupeReadOnlyCalc(path: string): boolean {
  const p = requestPathname(path);
  return p.includes("/mt5/order/calculate");
}

export function shouldHealSessionOnUnauthorized(args: {
  status: number;
  authEnabled: boolean;
  alreadyRetried: boolean;
}): boolean {
  return args.status === 401 && args.authEnabled && !args.alreadyRetried;
}

/**
 * Replay after refresh is GET/HEAD only.
 * Order submission is never blindly retried — unknown execution → reconcile.
 */
export function shouldReplayAfterRefresh(method: string, path: string): boolean {
  const m = (method || "GET").toUpperCase();
  if (m !== "GET" && m !== "HEAD") return false;
  const p = requestPathname(path);
  if (
    p.includes("/execution/submit") ||
    p.includes("/execution/cancel") ||
    p.includes("/execution/manage") ||
    p.includes("/mt5/order")
  ) {
    return false;
  }
  return true;
}

/** One refresh + one retry. Never loop. Mutating OMS paths do not auto-replay. */
export function shouldAttemptTokenRefresh(args: {
  status: number;
  authEnabled: boolean;
  alreadyRetried: boolean;
  method?: string;
  path?: string;
}): boolean {
  if (!shouldHealSessionOnUnauthorized(args)) return false;
  if (args.method || args.path) {
    return shouldReplayAfterRefresh(args.method || "GET", args.path || "/");
  }
  return true;
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

export function isUnreachableFailure(error: {
  status?: number;
  code?: string;
} | null | undefined): boolean {
  if (!error) return false;
  return error.code === "network_error" || error.status === 0;
}

export function isContractValidationFailure(error: {
  status?: number;
  code?: string;
} | null | undefined): boolean {
  if (!error) return false;
  return (
    error.status === 422 ||
    error.code === "request_validation_error" ||
    error.code === "CONTRACT_VALIDATION_ERROR"
  );
}
