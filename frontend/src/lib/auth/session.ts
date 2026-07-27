"use client";

/**
 * Session storage for Bearer tokens.
 *
 * Backend auth is Authorization: Bearer only — there is no Set-Cookie / HttpOnly
 * session API. Tokens therefore cannot move to HttpOnly cookies without a BFF
 * or API contract change (explicitly out of scope for GA readiness).
 *
 * Hardening within compatibility:
 * - Remember Me → localStorage (survive refresh/restart)
 * - Without Remember Me → sessionStorage (tab lifetime only)
 * - Clear both stores on logout
 * - Cross-tab logout via storage events
 * - Never return tokens from helpers used for display
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
const REMEMBER = "qf_remember_me";
const KEYS = [ACCESS, REFRESH, USER, REMEMBER] as const;

function scrubKey(store: Storage | null, key: string) {
  if (!store) return;
  try {
    store.removeItem(key);
  } catch {
    /* ignore */
  }
}

function preferredStore(remember?: boolean): Storage | null {
  if (typeof window === "undefined") return null;
  if (remember === false) return window.sessionStorage;
  if (remember === true) return window.localStorage;
  // Restore path: prefer localStorage if remember flag or access token present
  try {
    if (window.localStorage.getItem(REMEMBER) === "1") return window.localStorage;
    if (window.localStorage.getItem(ACCESS)) return window.localStorage;
    if (window.sessionStorage.getItem(ACCESS)) return window.sessionStorage;
  } catch {
    /* ignore */
  }
  return window.localStorage;
}

export function saveSession(session: AuthSession, options?: { remember?: boolean }) {
  if (typeof window === "undefined") return;
  const remember = options?.remember !== false;
  const store = remember ? window.localStorage : window.sessionStorage;
  const other = remember ? window.sessionStorage : window.localStorage;
  store.setItem(ACCESS, session.access_token);
  store.setItem(REFRESH, session.refresh_token);
  store.setItem(USER, JSON.stringify(session.user));
  store.setItem(REMEMBER, remember ? "1" : "0");
  for (const key of KEYS) scrubKey(other, key);
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
  return (
    window.localStorage.getItem(ACCESS) ||
    window.sessionStorage.getItem(ACCESS)
  );
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    window.localStorage.getItem(REFRESH) ||
    window.sessionStorage.getItem(REFRESH)
  );
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  const raw =
    window.localStorage.getItem(USER) || window.sessionStorage.getItem(USER);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function isRememberMeEnabled(): boolean {
  if (typeof window === "undefined") return true;
  const flag =
    window.localStorage.getItem(REMEMBER) ||
    window.sessionStorage.getItem(REMEMBER);
  if (flag === "0") return false;
  return true;
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

/** @internal — used by tests / diagnostics */
export function _preferredStoreForTests(remember?: boolean): Storage | null {
  return preferredStore(remember);
}
