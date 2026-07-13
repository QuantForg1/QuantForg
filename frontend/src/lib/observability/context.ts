/** Shared observability context for errors and client audit events. */

export type ObservabilityContext = {
  request_id: string;
  user_id: string | null;
  route: string;
  browser: string;
  build_version: string;
  environment: string;
  timestamp: string;
};

const BUILD_VERSION =
  process.env.NEXT_PUBLIC_BUILD_VERSION?.trim() ||
  process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA?.slice(0, 7) ||
  process.env.npm_package_version ||
  "1.0.0";

export function getBuildVersion() {
  return BUILD_VERSION;
}

export function newRequestId(prefix = "qf") {
  const rand =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
  return `${prefix}_${rand}`;
}

export function getBrowserInfo() {
  if (typeof navigator === "undefined") return "server";
  return navigator.userAgent.slice(0, 240);
}

export function getRoutePath() {
  if (typeof window === "undefined") return "/";
  return `${window.location.pathname}${window.location.search}`.slice(0, 300);
}

export function buildObservabilityContext(
  partial?: Partial<ObservabilityContext> & { userId?: string | null },
): ObservabilityContext {
  return {
    request_id: partial?.request_id || newRequestId(),
    user_id: partial?.user_id ?? partial?.userId ?? null,
    route: partial?.route || getRoutePath(),
    browser: partial?.browser || getBrowserInfo(),
    build_version: partial?.build_version || getBuildVersion(),
    environment:
      partial?.environment ||
      process.env.NEXT_PUBLIC_APP_ENV ||
      process.env.NODE_ENV ||
      "development",
    timestamp: partial?.timestamp || new Date().toISOString(),
  };
}

/** Strip secrets / credentials before logging or shipping. */
export function sanitizePayload(input: unknown): unknown {
  if (input == null) return input;
  if (typeof input !== "object") return input;
  if (Array.isArray(input)) return input.map(sanitizePayload);

  const blocked = /password|token|secret|authorization|cookie|api[_-]?key|refresh/i;
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(input as Record<string, unknown>)) {
    if (blocked.test(key)) {
      out[key] = "[redacted]";
      continue;
    }
    out[key] = sanitizePayload(value);
  }
  return out;
}
