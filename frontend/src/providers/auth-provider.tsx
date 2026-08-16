"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import {
  clearSession,
  getAccessToken,
  getStoredUser,
  onSessionCleared,
  saveSession,
  type AuthSession,
  type AuthUser,
} from "@/lib/auth/session";
import { recordAudit } from "@/lib/observability/audit";

/** Hard cap so AppShell never waits forever on /auth/me. */
const SESSION_BOOT_TIMEOUT_MS = 25_000;
/** One silent retry before surfacing AUTH_TIMEOUT (Railway cold starts). */
const SESSION_ME_RETRY_MS = 800;

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  bootError: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string, options?: { remember?: boolean }) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<string | void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Deterministic SSR/client first paint: never read localStorage during render.
  // Session is restored in useEffect so server HTML and client hydrate match.
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootError, setBootError] = useState<string | null>(null);

  const refreshMe = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setBootError(null);
      return;
    }
    const tryMe = async () => authApi.me();
    try {
      let me;
      try {
        me = await tryMe();
      } catch (first) {
        // Bounded single retry on timeout/transient — avoids false AUTH_TIMEOUT
        // during Railway cold start without infinite loops.
        if (
          first instanceof ApiError &&
          (first.code === "timeout" ||
            first.status === 502 ||
            first.status === 503 ||
            first.status === 504)
        ) {
          await new Promise((r) => window.setTimeout(r, SESSION_ME_RETRY_MS));
          me = await tryMe();
        } else {
          throw first;
        }
      }
      setUser(me);
      setBootError(null);
    } catch (e) {
      // Preserve session on transient network loss; only wipe on auth failure.
      if (
        e instanceof ApiError &&
        (e.status === 401 || e.status === 403 || e.code === "unauthorized")
      ) {
        clearSession();
        setUser(null);
        setBootError(null);
        return;
      }
      if (
        e instanceof ApiError &&
        (e.code === "network_error" ||
          e.code === "timeout" ||
          e.status === 408 ||
          e.status === 425 ||
          e.status === 429 ||
          e.status === 500 ||
          e.status === 502 ||
          e.status === 503 ||
          e.status === 504)
      ) {
        // Keep stored user for UI; ConnectionBanner / retry covers transient API errors.
        const stored = getStoredUser();
        setUser(stored);
        setBootError(
          e.code === "timeout"
            ? "Session check timed out. You can retry or sign in again."
            : "API unreachable. Retry when the connection recovers.",
        );
        if (e.code === "timeout") {
          recordAudit("session_timeout", "info", "auth_me_timeout");
        } else {
          recordAudit(
            "api_degraded",
            "info",
            e.code || `status_${e.status}`,
          );
        }
        return;
      }
      // Unknown non-ApiError (e.g. parse): keep session if tokens still present.
      if (!(e instanceof ApiError) && getAccessToken()) {
        const stored = getStoredUser();
        setUser(stored);
        return;
      }
      clearSession();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    const stored = getStoredUser();
    if (stored && getAccessToken()) {
      setUser(stored);
    }
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      setLoading(false);
    };
    const timer = window.setTimeout(() => {
      if (settled) return;
      setBootError((prev) => prev ?? "Session restore timed out. Retry or sign in again.");
      // Prefer stored user over infinite skeleton when /auth/me hangs.
      if (!getAccessToken()) {
        setUser(null);
      } else {
        setUser((u) => u ?? getStoredUser());
      }
      finish();
    }, SESSION_BOOT_TIMEOUT_MS);

    void refreshMe().finally(() => {
      window.clearTimeout(timer);
      finish();
    });
    return () => window.clearTimeout(timer);
  }, [refreshMe]);

  useEffect(() => {
    return onSessionCleared(() => {
      setUser(null);
      setBootError(null);
    });
  }, []);

  const login = useCallback(async (email: string, password: string, options?: { remember?: boolean }) => {
    try {
      const session = await authApi.login(email, password);
      saveSession(session, { remember: options?.remember !== false });
      setUser(session.user);
      setBootError(null);
      recordAudit("login", "success", "User signed in", { email });
    } catch (e) {
      recordAudit("login", "failure", "Sign-in failed", { email });
      throw e;
    }
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      try {
        const result = await authApi.register(email, password, displayName);
        if ("access_token" in result) {
          saveSession(result as AuthSession);
          setUser((result as AuthSession).user);
          setBootError(null);
          recordAudit("register", "success", "Account registered", { email });
          return;
        }
        recordAudit("register", "info", "Registration pending verification", { email });
        return result.message;
      } catch (e) {
        recordAudit("register", "failure", "Registration failed", { email });
        throw e;
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
      recordAudit("logout", "success", "User signed out");
    } catch {
      recordAudit("logout", "info", "Sign-out completed locally after API error");
    }
    clearSession();
    setUser(null);
    setBootError(null);
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      bootError,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      refreshMe,
    }),
    [user, loading, bootError, login, register, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
