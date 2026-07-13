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
import {
  clearSession,
  getAccessToken,
  getStoredUser,
  saveSession,
  type AuthSession,
  type AuthUser,
} from "@/lib/auth/session";
import { recordAudit } from "@/lib/observability/audit";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<string | void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const stored = getStoredUser();
    return stored && getAccessToken() ? stored : null;
  });
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      return;
    }
    try {
      const me = await authApi.me();
      setUser(me);
    } catch {
      clearSession();
      setUser(null);
    }
  }, []);

  useEffect(() => {
    refreshMe().finally(() => setLoading(false));
  }, [refreshMe]);

  const login = useCallback(async (email: string, password: string) => {
    try {
      const session = await authApi.login(email, password);
      saveSession(session);
      setUser(session.user);
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
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      login,
      register,
      logout,
      refreshMe,
    }),
    [user, loading, login, register, logout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
