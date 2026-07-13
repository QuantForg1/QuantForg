import { apiFetch } from "@/lib/api/client";
import type { AuthSession, AuthUser } from "@/lib/auth/session";
import { env } from "@/lib/env";

export const authApi = {
  login: (email: string, password: string) =>
    apiFetch<AuthSession>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  register: (email: string, password: string, display_name: string) =>
    apiFetch<AuthSession | { message: string }>("/auth/register", {
      method: "POST",
      body: { email, password, display_name },
      auth: false,
    }),
  logout: () =>
    apiFetch<{ message: string }>("/auth/logout", { method: "POST", body: {} }),
  me: () => apiFetch<AuthUser>("/auth/me"),
  forgotPassword: (email: string, redirect_to?: string) =>
    apiFetch<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: { email, redirect_to },
      auth: false,
    }),
  verifyEmail: (token_hash: string, type = "email") =>
    apiFetch<AuthSession | { message: string }>("/auth/verify-email", {
      method: "POST",
      body: { token_hash, type },
      auth: false,
    }),
  changePassword: (new_password: string) =>
    apiFetch<{ message: string }>("/auth/change-password", {
      method: "POST",
      body: { new_password },
    }),
};

export const portfolioApi = {
  get: () => apiFetch<Record<string, unknown>>("/portfolio"),
  positions: (symbol?: string) =>
    apiFetch<unknown[]>(
      symbol ? `/positions?symbol=${encodeURIComponent(symbol)}` : "/positions",
    ),
  orders: () => apiFetch<unknown[]>("/orders"),
  history: () => apiFetch<Record<string, unknown>>("/history"),
};

export const mt5Api = {
  status: () => apiFetch<Record<string, unknown>>("/mt5/status"),
  connect: (body: {
    login: number;
    password: string;
    server: string;
    path?: string;
  }) => apiFetch<Record<string, unknown>>("/mt5/connect", { method: "POST", body }),
  disconnect: () =>
    apiFetch<Record<string, unknown>>("/mt5/disconnect", { method: "POST", body: {} }),
  account: () => apiFetch<Record<string, unknown>>("/mt5/account"),
  symbols: () => apiFetch<unknown[]>("/mt5/symbols"),
  symbol: (symbol: string) =>
    apiFetch<Record<string, unknown>>(`/mt5/symbols/${encodeURIComponent(symbol)}`),
  tick: (symbol: string) =>
    apiFetch<Record<string, unknown>>(`/mt5/ticks/${encodeURIComponent(symbol)}`),
  candles: (symbol: string, timeframe = "H1", count = 48) =>
    apiFetch<unknown[]>(
      `/mt5/candles/${encodeURIComponent(symbol)}?timeframe=${encodeURIComponent(timeframe)}&count=${count}`,
    ),
  validateOrder: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/mt5/order/validate", {
      method: "POST",
      body,
    }),
  calculateOrder: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/mt5/order/calculate", {
      method: "POST",
      body,
    }),
};

export const brokersApi = {
  list: () => apiFetch<unknown[]>("/brokers"),
  health: (id: string) => apiFetch<Record<string, unknown>>(`/brokers/${id}/health`),
  accounts: () => apiFetch<unknown[]>("/broker-accounts"),
  connections: () => apiFetch<unknown[]>("/broker-connections"),
};

export const riskApi = {
  check: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/risk/check", { method: "POST", body }),
};

export const strategyApi = {
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy/evaluate", {
      method: "POST",
      body,
    }),
  signals: () => apiFetch<Record<string, unknown>>("/strategy/signals"),
};

export const backtestApi = {
  run: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/backtests/run", { method: "POST", body }),
  list: () => apiFetch<Record<string, unknown>>("/backtests"),
  get: (id: string) => apiFetch<Record<string, unknown>>(`/backtests/${id}`),
};

export const paperApi = {
  place: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/paper/orders", { method: "POST", body }),
  positions: () => apiFetch<Record<string, unknown>>("/paper/positions"),
  history: () => apiFetch<Record<string, unknown>>("/paper/history"),
  performance: () => apiFetch<Record<string, unknown>>("/paper/performance"),
};

export const walkforwardApi = {
  list: () => apiFetch<Record<string, unknown>>("/walkforward/results"),
  get: (id: string) =>
    apiFetch<Record<string, unknown>>(`/walkforward/${id}`),
  run: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/walkforward/run", {
      method: "POST",
      body,
    }),
};

export const executionApi = {
  check: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/execution/check", { method: "POST", body }),
  submit: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/execution/submit", { method: "POST", body }),
};

export const opsApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/ops/dashboard"),
  metrics: () => apiFetch<Record<string, unknown>>("/ops/metrics"),
  alerts: () => apiFetch<Record<string, unknown>>("/ops/alerts"),
  audit: () => apiFetch<Record<string, unknown>>("/ops/audit"),
};

export const platformApi = {
  notifications: (unread_only = false) =>
    apiFetch<unknown[]>(
      unread_only ? "/notifications?unread_only=true" : "/notifications",
    ),
  markNotificationRead: (id: string) =>
    apiFetch<Record<string, unknown>>(`/notifications/${id}/read`, {
      method: "POST",
      body: {},
    }),
  notificationPreferences: () =>
    apiFetch<unknown[]>("/notifications/preferences"),
  organizations: () => apiFetch<unknown[]>("/organizations"),
  createOrganization: (body: { name: string; slug: string }) =>
    apiFetch<Record<string, unknown>>("/organizations", {
      method: "POST",
      body,
    }),
  inviteMember: (organizationId: string, body: { email: string; role?: string }) =>
    apiFetch<Record<string, unknown>>(
      `/organizations/${organizationId}/invitations`,
      { method: "POST", body },
    ),
  profile: () => apiFetch<Record<string, unknown>>("/profile"),
  updateProfile: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/profile", { method: "PATCH", body }),
  activity: () => apiFetch<unknown[]>("/profile/activity"),
  settings: () => apiFetch<Record<string, unknown>>("/settings"),
  updateSettings: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/settings", { method: "PATCH", body }),
  devices: () => apiFetch<unknown[]>("/settings/devices"),
  sessions: () => apiFetch<unknown[]>("/settings/sessions"),
  revokeSession: (sessionId: string) =>
    apiFetch<Record<string, unknown>>(`/settings/sessions/${sessionId}/revoke`, {
      method: "POST",
      body: {},
    }),
  version: () => apiFetch<Record<string, unknown>>("/version"),
  health: () =>
    apiFetch<Record<string, unknown>>(
      `${env.apiBaseUrl.replace(/\/api\/v1$/, "")}/health`,
      { auth: false },
    ),
  healthLive: () =>
    apiFetch<Record<string, unknown>>(
      `${env.apiBaseUrl.replace(/\/api\/v1$/, "")}/health/live`,
      { auth: false },
    ),
};
