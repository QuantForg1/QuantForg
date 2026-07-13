"use client";

/**
 * Session storage for Bearer tokens.
 *
 * Backend auth is Authorization: Bearer only — there is no Set-Cookie / HttpOnly
 * session API. Tokens therefore cannot move to HttpOnly cookies without a BFF
 * or API contract change (explicitly out of scope for GA readiness).
 *
 * Hardening within compatibility:
 * - Clear both localStorage and sessionStorage mirrors on logout
 * - Cross-tab logout via storage events
 * - Never return tokens from helpers used for display
 * - Migrate legacy keys and scrub duplicates
 */

export type AuthUser = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  status: string;
  auth_user_id?: string | null;
};

export type AuthSession = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  token_type: string;
  user: AuthUser;
};

const ACCESS = "qf_access_token";
const REFRESH = "qf_refresh_token";
const USER = "qf_user";
const KEYS = [ACCESS, REFRESH, USER] as const;

function browserStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  return window.localStorage;
}

function scrubKey(store: Storage | null, key: string) {
  if (!store) return;
  try {
    store.removeItem(key);
  } catch {
    /* ignore */
  }
}

export function saveSession(session: AuthSession) {
  const store = browserStorage();
  if (!store) return;
  store.setItem(ACCESS, session.access_token);
  store.setItem(REFRESH, session.refresh_token);
  store.setItem(USER, JSON.stringify(session.user));
  // Avoid lingering copies in sessionStorage from earlier experiments.
  if (typeof window !== "undefined") {
    for (const key of KEYS) scrubKey(window.sessionStorage, key);
  }
}

export function clearSession() {
  if (typeof window === "undefined") return;
  for (const key of KEYS) {
    scrubKey(window.localStorage, key);
    scrubKey(window.sessionStorage, key);
  }
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

/** Subscribe to cross-tab logout / session wipe. */
export function onSessionCleared(cb: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  const handler = (ev: StorageEvent) => {
    if (ev.storageArea !== window.localStorage) return;
    if (ev.key === ACCESS && ev.newValue == null) cb();
    if (ev.key === null) cb();
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}
