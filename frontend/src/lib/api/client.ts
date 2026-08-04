import { env } from "@/lib/env";
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  isRememberMeEnabled,
  saveSession,
  type AuthSession,
} from "@/lib/auth/session";
import {
  isNetworkFailure,
  markApiReachable,
  noteApiNetworkFailure,
  noteApiTimeout,
} from "@/lib/api/connectivity";
import { newRequestId } from "@/lib/observability/context";
import { captureError } from "@/lib/observability/error-monitor";
import { recordApiRequestSample } from "@/lib/api/request-log";

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;
  requestId?: string;

  constructor(
    message: string,
    status: number,
    code?: string,
    details?: unknown,
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

/** Default hard timeout so UI never spins forever on a hung API. */
export const API_DEFAULT_TIMEOUT_MS = 25_000;
export const API_AUTH_TIMEOUT_MS = 15_000;
export const API_HEALTH_TIMEOUT_MS = 8_000;
export const API_HEAVY_TIMEOUT_MS = 45_000;

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
  auth?: boolean;
  signal?: AbortSignal;
  /** Override default request timeout (ms). 0 disables. */
  timeoutMs?: number;
  /** Observability classification for failed calls */
  errorKind?: "api" | "execution" | "mt5";
  /** Skip error-monitor logging (still throws). */
  silent?: boolean;
};

function mergeAbortSignals(
  external: AbortSignal | undefined,
  timeoutMs: number,
): { signal: AbortSignal | undefined; cleanup: () => void } {
  if (timeoutMs <= 0 && !external) {
    return { signal: undefined, cleanup: () => undefined };
  }
  if (timeoutMs <= 0) {
    return { signal: external, cleanup: () => undefined };
  }
  const timeoutSignal =
    typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function"
      ? AbortSignal.timeout(timeoutMs)
      : undefined;
  if (!timeoutSignal && !external) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return {
      signal: controller.signal,
      cleanup: () => clearTimeout(timer),
    };
  }
  if (!external) {
    return { signal: timeoutSignal, cleanup: () => undefined };
  }
  if (!timeoutSignal) {
    return { signal: external, cleanup: () => undefined };
  }
  if (typeof AbortSignal.any === "function") {
    return { signal: AbortSignal.any([external, timeoutSignal]), cleanup: () => undefined };
  }
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  external.addEventListener("abort", onAbort);
  timeoutSignal.addEventListener("abort", onAbort);
  if (external.aborted || timeoutSignal.aborted) controller.abort();
  return {
    signal: controller.signal,
    cleanup: () => {
      external.removeEventListener("abort", onAbort);
      timeoutSignal.removeEventListener("abort", onAbort);
    },
  };
}

function isAbortError(err: unknown): boolean {
  if (!err || typeof err !== "object") return false;
  const name = "name" in err ? String((err as { name?: unknown }).name) : "";
  return name === "AbortError" || name === "TimeoutError";
}

async function parseError(res: Response, requestId: string) {
  let payload: Record<string, unknown> = {};
  try {
    payload = (await res.json()) as Record<string, unknown>;
  } catch {
    /* ignore */
  }
  const err = (payload.error as Record<string, unknown> | undefined) || payload;
  const message =
    (typeof err.message === "string" && err.message) ||
    (typeof payload.message === "string" && payload.message) ||
    res.statusText ||
    "Request failed";
  const code = typeof err.code === "string" ? err.code : undefined;
  const serverRequestId =
    (typeof payload.request_id === "string" && payload.request_id) ||
    (typeof err.request_id === "string" && err.request_id) ||
    requestId;
  throw new ApiError(message, res.status, code, err.details ?? payload, serverRequestId);
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;
  const { signal, cleanup } = mergeAbortSignals(undefined, API_AUTH_TIMEOUT_MS);
  try {
    const res = await fetch(`${env.apiBaseUrl}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
      signal,
    });
    if (!res.ok) {
      clearSession();
      return null;
    }
    const session = (await res.json()) as AuthSession;
    // Preserve Remember Me storage preference across refresh (do not force localStorage).
    saveSession(session, { remember: isRememberMeEnabled() });
    markApiReachable();
    return session.access_token;
  } catch (err) {
    if (isAbortError(err)) noteApiTimeout();
    else noteApiNetworkFailure();
    return null;
  } finally {
    cleanup();
  }
}

function classifyPath(path: string): "api" | "execution" | "mt5" {
  if (path.includes("/execution")) return "execution";
  if (path.includes("/mt5")) return "mt5";
  return "api";
}

function toNetworkApiError(err: unknown, requestId: string): ApiError {
  if (err instanceof ApiError && err.code === "network_error") return err;
  if (isAbortError(err)) {
    return new ApiError(
      "Request timed out. The API did not respond in time — retry shortly.",
      408,
      "timeout",
      { cause: err instanceof Error ? err.message : String(err) },
      requestId,
    );
  }
  return new ApiError(
    "Unable to reach the QuantForg API. Check connection and API base URL.",
    0,
    "network_error",
    { cause: err instanceof Error ? err.message : String(err) },
    requestId,
  );
}

function defaultTimeoutForPath(path: string): number {
  const p = path.startsWith("http") ? new URL(path).pathname : path;
  if (
    p.includes("/auth/login") ||
    p.includes("/auth/refresh") ||
    p.includes("/auth/me")
  ) {
    return API_AUTH_TIMEOUT_MS;
  }
  if (p.endsWith("/health") || p.includes("/health/") || p.endsWith("/health/live")) {
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

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, auth = true, signal, silent = false } = options;
  const requestId = newRequestId("req");
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-Request-ID": requestId,
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let token = options.token;
  if (auth && token === undefined) token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const url = path.startsWith("http") ? path : `${env.apiBaseUrl}${path}`;
  const safePath = path.startsWith("http") ? new URL(path).pathname : path;
  const kind = options.errorKind || classifyPath(safePath);
  const timeoutMs =
    options.timeoutMs !== undefined ? options.timeoutMs : defaultTimeoutForPath(safePath);
  const { signal: effectiveSignal, cleanup } = mergeAbortSignals(signal, timeoutMs);
  const started = performance.now();
  let retries = 0;

  const record = (partial: {
    status: number;
    sizeBytes?: number | null;
    timedOut?: boolean;
    error?: string;
  }) => {
    if (silent && partial.status >= 200 && partial.status < 400) return;
    recordApiRequestSample({
      method,
      path: safePath,
      status: partial.status,
      latencyMs: Math.round(performance.now() - started),
      sizeBytes: partial.sizeBytes ?? null,
      retries,
      timedOut: Boolean(partial.timedOut),
      error: partial.error,
      requestId,
    });
  };

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: effectiveSignal,
    });
  } catch (err) {
    cleanup();
    const networkErr = toNetworkApiError(err, requestId);
    if (networkErr.code === "timeout") noteApiTimeout();
    else noteApiNetworkFailure();
    record({
      status: networkErr.status,
      timedOut: networkErr.code === "timeout",
      error: networkErr.message,
    });
    if (!silent) {
      captureError(kind, networkErr, {
        request_id: requestId,
        path: safePath,
        status: networkErr.status,
        details: { network: true, timeout: networkErr.code === "timeout" },
      });
    }
    throw networkErr;
  }

  markApiReachable();

  if (res.status === 401 && auth) {
    if (!refreshPromise) {
      refreshPromise = refreshAccessToken().finally(() => {
        refreshPromise = null;
      });
    }
    const next = await refreshPromise;
    if (next) {
      retries += 1;
      headers.Authorization = `Bearer ${next}`;
      try {
        res = await fetch(url, {
          method,
          headers,
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: effectiveSignal,
        });
        markApiReachable();
      } catch (err) {
        cleanup();
        const networkErr = toNetworkApiError(err, requestId);
        if (networkErr.code === "timeout") noteApiTimeout();
        else noteApiNetworkFailure();
        record({
          status: networkErr.status,
          timedOut: networkErr.code === "timeout",
          error: networkErr.message,
        });
        if (!silent) {
          captureError(kind, networkErr, {
            request_id: requestId,
            path: safePath,
            status: networkErr.status,
            details: { network: true, phase: "retry_after_refresh" },
          });
        }
        throw networkErr;
      }
    }
  }

  cleanup();

  const sizeHeader = res.headers.get("content-length");
  const sizeBytes = sizeHeader ? Number(sizeHeader) : null;

  if (!res.ok) {
    try {
      await parseError(res, requestId);
    } catch (e) {
      const apiErr = e instanceof ApiError ? e : null;
      record({
        status: res.status,
        sizeBytes: Number.isFinite(sizeBytes) ? sizeBytes : null,
        error: apiErr?.message || (e instanceof Error ? e.message : "Request failed"),
      });
      if (!silent) {
        captureError(kind, e, {
          request_id: apiErr?.requestId || requestId,
          status: res.status,
          path: safePath,
          details: apiErr?.details,
        });
      }
      throw e;
    }
  }

  if (res.status === 204) {
    record({ status: 204, sizeBytes: 0 });
    return undefined as T;
  }
  const text = await res.text();
  record({
    status: res.status,
    sizeBytes: text.length || (Number.isFinite(sizeBytes) ? sizeBytes : null),
  });
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export { isNetworkFailure };
