import { env } from "@/lib/env";
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  saveSession,
  type AuthSession,
} from "@/lib/auth/session";
import { newRequestId } from "@/lib/observability/context";
import { captureError } from "@/lib/observability/error-monitor";

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

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
  auth?: boolean;
  signal?: AbortSignal;
  /** Observability classification for failed calls */
  errorKind?: "api" | "execution" | "mt5";
};

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
  const res = await fetch(`${env.apiBaseUrl}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!res.ok) {
    clearSession();
    return null;
  }
  const session = (await res.json()) as AuthSession;
  saveSession(session);
  return session.access_token;
}

function classifyPath(path: string): "api" | "execution" | "mt5" {
  if (path.includes("/execution")) return "execution";
  if (path.includes("/mt5")) return "mt5";
  return "api";
}

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, auth = true, signal } = options;
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

  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (err) {
    captureError(kind, err, { request_id: requestId, path: safePath });
    throw err;
  }

  if (res.status === 401 && auth) {
    if (!refreshPromise) refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
    const next = await refreshPromise;
    if (next) {
      headers.Authorization = `Bearer ${next}`;
      res = await fetch(url, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal,
      });
    }
  }

  if (!res.ok) {
    try {
      await parseError(res, requestId);
    } catch (e) {
      const apiErr = e instanceof ApiError ? e : null;
      captureError(kind, e, {
        request_id: apiErr?.requestId || requestId,
        status: res.status,
        path: safePath,
        details: apiErr?.details,
      });
      throw e;
    }
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
