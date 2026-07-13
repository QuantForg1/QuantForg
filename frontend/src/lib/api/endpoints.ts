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
  signals: () => apiFetch<unknown[]>("/strategy/signals"),
};

export const backtestApi = {
  run: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/backtests/run", { method: "POST", body }),
  list: () => apiFetch<unknown[]>("/backtests"),
  get: (id: string) => apiFetch<Record<string, unknown>>(`/backtests/${id}`),
};

export const paperApi = {
  place: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/paper/orders", { method: "POST", body }),
  positions: () => apiFetch<unknown[]>("/paper/positions"),
  history: () => apiFetch<unknown[]>("/paper/history"),
  performance: () => apiFetch<Record<string, unknown>>("/paper/performance"),
};

export const walkforwardApi = {
  list: () => apiFetch<Record<string, unknown>>("/walkforward/results"),
  get: (id: string) =>
    apiFetch<Record<string, unknown>>(`/walkforward/results/${id}`),
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
};

export const platformApi = {
  notifications: () => apiFetch<unknown[]>("/notifications"),
  organizations: () => apiFetch<unknown[]>("/organizations"),
  profile: () => apiFetch<Record<string, unknown>>("/profile"),
  settings: () => apiFetch<Record<string, unknown>>("/settings"),
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
