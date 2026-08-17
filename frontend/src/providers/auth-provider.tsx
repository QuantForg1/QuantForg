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
import { ApiError, API_AUTH_TIMEOUT_MS } from "@/lib/api/client";
import { sessionBootBudgetMs } from "@/lib/api/request-policy";
import {
  authBootBanner,
  canIssueProtectedOps,
  isAuthenticatedPhase,
  resolveAuthPhase,
  type AuthPhase,
  type MeAttemptStatus,
} from "@/lib/auth/bootstrap";
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

/** One silent background retry after AUTH_TIMEOUT (Railway cold starts). */
const SESSION_ME_RETRY_MS = 800;

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  bootError: string | null;
  isAuthenticated: boolean;
  authPhase: AuthPhase;
  /** True only after /auth/me settled (success or timeout-with-token). */
  opsReady: boolean;
  login: (email: string, password: string, options?: { remember?: boolean }) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<string | void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Deterministic SSR/client first paint: never read localStorage during render.
  const [user, setUser] = useState<AuthUser | null>(null);
  const [hasToken, setHasToken] = useState(false);
  const [loading, setLoading] = useState(true);
  const [meStatus, setMeStatus] = useState<MeAttemptStatus>("idle");
  const [bootError, setBootError] = useState<string | null>(null);

  const refreshMe = useCallback(async (opts?: { background?: boolean }) => {
    const token = getAccessToken();
    if (!token) {
      setHasToken(false);
      setUser(null);
      setMeStatus("unauthorized");
      setBootError(null);
      return;
    }
    setHasToken(true);
    try {
      const me = await authApi.me();
      setUser(me);
      setMeStatus("success");
      setBootError(null);
    } catch (e) {
      if (
        e instanceof ApiError &&
        (e.status === 401 || e.status === 403 || e.code === "unauthorized")
      ) {
        clearSession();
        setHasToken(false);
        setUser(null);
        setMeStatus("unauthorized");
        setBootError(null);
        return;
      }
      const transient =
        e instanceof ApiError &&
        (e.code === "network_error" ||
          e.code === "timeout" ||
          e.status === 408 ||
          e.status === 425 ||
          e.status === 429 ||
          e.status === 500 ||
          e.status === 502 ||
          e.status === 503 ||
          e.status === 504);
      if (transient) {
        const stored = getStoredUser();
        const stillHasToken = Boolean(getAccessToken());
        setHasToken(stillHasToken);
        setUser(stored);
        const timedOut = e instanceof ApiError && e.code === "timeout";
        setMeStatus(timedOut ? "timeout" : "error");
        if (stillHasToken && stored) {
          setBootError(authBootBanner("AUTH_TIMEOUT"));
          if (timedOut) {
            recordAudit("session_timeout", "info", "auth_me_timeout");
          } else {
            recordAudit("api_degraded", "info", e instanceof ApiError ? e.code || `status_${e.status}` : "error");
          }
          if (!opts?.background) {
            window.setTimeout(() => {
              void refreshMe({ background: true });
            }, SESSION_ME_RETRY_MS);
          }
          return;
        }
        setMeStatus("unauthorized");
        setBootError("Sign in required.");
        return;
      }
      if (!(e instanceof ApiError) && getAccessToken()) {
        const stored = getStoredUser();
        setHasToken(true);
        setUser(stored);
        setMeStatus(stored ? "error" : "unauthorized");
        return;
      }
      clearSession();
      setHasToken(false);
      setUser(null);
      setMeStatus("unauthorized");
    }
  }, []);

  useEffect(() => {
    // Restore token presence only — do not mark authenticated until /auth/me settles.
    setHasToken(Boolean(getAccessToken()));
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      setLoading(false);
    };
    const timer = window.setTimeout(() => {
      if (settled) return;
      const stored = getStoredUser();
      const token = getAccessToken();
      if (token && stored) {
        setHasToken(true);
        setUser((u) => u ?? stored);
        setMeStatus((prev) => (prev === "success" ? prev : "timeout"));
        setBootError((prev) => prev ?? authBootBanner("AUTH_TIMEOUT"));
      } else if (!token) {
        setHasToken(false);
        setUser(null);
        setMeStatus("unauthorized");
      }
      finish();
    }, sessionBootBudgetMs(API_AUTH_TIMEOUT_MS));

    void refreshMe().finally(() => {
      window.clearTimeout(timer);
      finish();
    });
    return () => window.clearTimeout(timer);
  }, [refreshMe]);

  useEffect(() => {
    return onSessionCleared(() => {
      setUser(null);
      setHasToken(false);
      setMeStatus("unauthorized");
      setBootError(null);
    });
  }, []);

  const login = useCallback(async (email: string, password: string, options?: { remember?: boolean }) => {
    try {
      const session = await authApi.login(email, password);
      saveSession(session, { remember: options?.remember !== false });
      setHasToken(true);
      setUser(session.user);
      setMeStatus("success");
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
          setHasToken(true);
          setUser((result as AuthSession).user);
          setMeStatus("success");
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
    setHasToken(false);
    setUser(null);
    setMeStatus("unauthorized");
    setBootError(null);
  }, []);

  const authPhase = resolveAuthPhase({
    loading,
    hasToken,
    hasUser: Boolean(user),
    meStatus,
  });
  const opsReady = canIssueProtectedOps(authPhase, hasToken);
  const isAuthenticated = isAuthenticatedPhase(authPhase, Boolean(user));

  const value = useMemo(
    () => ({
      user,
      loading,
      bootError,
      isAuthenticated,
      authPhase,
      opsReady,
      login,
      register,
      logout,
      refreshMe: () => refreshMe(),
    }),
    [user, loading, bootError, isAuthenticated, authPhase, opsReady, login, register, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
