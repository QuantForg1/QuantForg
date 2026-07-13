import { env } from "@/lib/env";
import {
  clearSession,
  getAccessToken,
  getRefreshToken,
  saveSession,
  type AuthSession,
} from "@/lib/auth/session";

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
  auth?: boolean;
  signal?: AbortSignal;
};

async function parseError(res: Response) {
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
  throw new ApiError(message, res.status, code, err.details ?? payload);
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

export async function apiFetch<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, auth = true, signal } = options;
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let token = options.token;
  if (auth && token === undefined) token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const url = path.startsWith("http") ? path : `${env.apiBaseUrl}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (err) {
    const safePath = path.startsWith("http") ? new URL(path).pathname : path;
    console.error("api_network_error", {
      path: safePath,
      method,
      message: err instanceof Error ? err.message : "network_error",
    });
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
    const safePath = path.startsWith("http") ? new URL(path).pathname : path;
    console.error("api_request_failed", {
      path: safePath,
      method,
      status: res.status,
    });
    await parseError(res);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
