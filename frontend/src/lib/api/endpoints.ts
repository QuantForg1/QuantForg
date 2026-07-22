import { apiFetch } from "@/lib/api/client";
import type { AuthSession, AuthUser } from "@/lib/auth/session";
import { env } from "@/lib/env";
import { asList, asRecord } from "@/lib/desk";
import {
  filterTradingSymbolRecords,
  goldOnlySearchQuery,
  MULTI_SYMBOL_ENABLED,
  resolveTradingSymbol,
  TRADING_SYMBOL,
} from "@/lib/trading/gold-only";

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
  historyRange: (params: { date_from?: string; date_to?: string }) => {
    const qs = new URLSearchParams();
    if (params.date_from) qs.set("date_from", params.date_from);
    if (params.date_to) qs.set("date_to", params.date_to);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return apiFetch<Record<string, unknown>>(`/history${suffix}`);
  },
};

type Mt5SymbolsPage = {
  items: unknown[];
  total: number;
  offset: number;
  limit: number;
  has_more: boolean;
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
  symbols: async (params?: {
    q?: string;
    offset?: number;
    limit?: number;
    include_quotes?: boolean;
  }): Promise<Mt5SymbolsPage> => {
    const offset = params?.offset ?? 0;
    const limit = params?.limit ?? 100;
    const include_quotes = params?.include_quotes ?? false;

    if (!MULTI_SYMBOL_ENABLED) {
      const q = goldOnlySearchQuery(params?.q);
      if (q === null) {
        return { items: [], total: 0, offset, limit, has_more: false };
      }
      const search = new URLSearchParams({
        offset: String(offset),
        limit: String(limit),
        include_quotes: include_quotes ? "true" : "false",
        q,
      });
      const page = await apiFetch<Mt5SymbolsPage>(`/mt5/symbols?${search.toString()}`);
      const items = filterTradingSymbolRecords(asList(page.items).map(asRecord));
      return {
        ...page,
        items,
        total: items.length,
        has_more: false,
      };
    }

    const q = params?.q?.trim() ?? "";
    const search = new URLSearchParams({
      offset: String(offset),
      limit: String(limit),
      include_quotes: include_quotes ? "true" : "false",
    });
    if (q) search.set("q", q);
    return apiFetch<Mt5SymbolsPage>(`/mt5/symbols?${search.toString()}`);
  },
  symbol: (symbol: string) =>
    apiFetch<Record<string, unknown>>(
      `/mt5/symbols/${encodeURIComponent(resolveTradingSymbol(symbol))}`,
    ),
  tick: (symbol: string) =>
    apiFetch<Record<string, unknown>>(
      `/mt5/ticks/${encodeURIComponent(resolveTradingSymbol(symbol))}`,
    ),
  candles: (symbol: string, timeframe = "H1", count = 48) =>
    apiFetch<unknown[]>(
      `/mt5/candles/${encodeURIComponent(resolveTradingSymbol(symbol))}?timeframe=${encodeURIComponent(timeframe)}&count=${count}`,
    ),
  validateOrder: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/mt5/order/validate", {
      method: "POST",
      body: {
        ...body,
        symbol: resolveTradingSymbol(String(body.symbol ?? "")),
      },
    }),
  calculateOrder: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/mt5/order/calculate", {
      method: "POST",
      body: {
        ...body,
        symbol: resolveTradingSymbol(String(body.symbol ?? "")),
      },
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

export const portfolioIntelligenceApi = {
  dashboard: (confidence = 0.95) =>
    apiFetch<Record<string, unknown>>(
      `/portfolio-intelligence/dashboard?confidence=${confidence}`,
    ),
  risk: () => apiFetch<Record<string, unknown>>("/portfolio-intelligence/risk"),
  stress: () => apiFetch<Record<string, unknown>>("/portfolio-intelligence/stress"),
  correlation: () =>
    apiFetch<Record<string, unknown>>("/portfolio-intelligence/correlation"),
  journal: () =>
    apiFetch<Record<string, unknown>>("/portfolio-intelligence/journal"),
  attribution: () =>
    apiFetch<Record<string, unknown>>("/portfolio-intelligence/attribution"),
  optimize: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/portfolio-intelligence/optimize", {
      method: "POST",
      body,
    }),
  analyze: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/portfolio-intelligence/analyze", {
      method: "POST",
      body,
    }),
};

export const strategyApi = {
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy/evaluate", {
      method: "POST",
      body: { ...body, symbol: resolveTradingSymbol(String(body.symbol ?? "")) },
    }),
  signals: () => apiFetch<Record<string, unknown>>("/strategy/signals"),
  catalog: () => apiFetch<Record<string, unknown>>("/strategy/catalog"),
  engineValidate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy/engine/validate", {
      method: "POST",
      body,
    }),
  engineRun: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy/engine/run", {
      method: "POST",
      body,
    }),
  portfolio: () => apiFetch<Record<string, unknown>>("/strategy/portfolio"),
  setAllocations: (allocations: unknown[]) =>
    apiFetch<Record<string, unknown>>("/strategy/portfolio/allocations", {
      method: "PUT",
      body: { allocations },
    }),
};

export const backtestApi = {
  run: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/backtests/run", {
      method: "POST",
      body: { ...body, symbol: resolveTradingSymbol(String(body.symbol ?? "")) },
    }),
  list: () => apiFetch<Record<string, unknown>>("/backtests"),
  get: (id: string) => apiFetch<Record<string, unknown>>(`/backtests/${id}`),
};

export const paperApi = {
  place: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/paper/orders", {
      method: "POST",
      body: { ...body, symbol: resolveTradingSymbol(String(body.symbol ?? "")) },
    }),
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
      body: { ...body, symbol: resolveTradingSymbol(String(body.symbol ?? "")) },
    }),
};

export const executionApi = {
  check: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/execution/check", {
      method: "POST",
      body: { ...body, symbol: resolveTradingSymbol(String(body.symbol ?? "")) },
    }),
  submit: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/execution/submit", {
      method: "POST",
      body: { ...body, symbol: resolveTradingSymbol(String(body.symbol ?? "")) },
    }),
  cancel: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/execution/cancel", { method: "POST", body }),
  manage: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/execution/manage", { method: "POST", body }),
  journal: (limit = 100) =>
    apiFetch<Record<string, unknown>>(`/execution/journal?limit=${limit}`),
  analytics: (limit = 200) =>
    apiFetch<Record<string, unknown>>(`/execution/analytics?limit=${limit}`),
  audits: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/execution/audits?limit=${limit}`),
  auditsByRequest: (requestId: string) =>
    apiFetch<Record<string, unknown>>(
      `/execution/audits/by-request/${encodeURIComponent(requestId)}`,
    ),
};

export const executionIntelligenceApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/execution-intelligence/dashboard"),
  lifecycle: (includeArchived = true) =>
    apiFetch<Record<string, unknown>>(
      `/execution-intelligence/lifecycle?include_archived=${includeArchived}`,
    ),
  observe: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/execution-intelligence/lifecycle/observe", {
      method: "POST",
      body,
    }),
  checklist: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/execution-intelligence/checklist", {
      method: "POST",
      body,
    }),
  analytics: () =>
    apiFetch<Record<string, unknown>>("/execution-intelligence/analytics"),
  postTrade: () =>
    apiFetch<Record<string, unknown>>("/execution-intelligence/post-trade"),
  broker: () =>
    apiFetch<Record<string, unknown>>("/execution-intelligence/broker"),
};

export const brokerConnectivityApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/broker-connectivity/dashboard"),
  catalog: () =>
    apiFetch<Record<string, unknown>>("/broker-connectivity/catalog"),
  matrix: () =>
    apiFetch<Record<string, unknown>>("/broker-connectivity/matrix"),
  diagnostics: (platform?: string) =>
    apiFetch<Record<string, unknown>>(
      platform
        ? `/broker-connectivity/diagnostics?platform=${encodeURIComponent(platform)}`
        : "/broker-connectivity/diagnostics",
    ),
  invoke: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/broker-connectivity/invoke", {
      method: "POST",
      body,
    }),
  health: (platform: string) =>
    apiFetch<Record<string, unknown>>(
      `/broker-connectivity/${encodeURIComponent(platform)}/health`,
    ),
  heartbeat: (platform: string) =>
    apiFetch<Record<string, unknown>>(
      `/broker-connectivity/${encodeURIComponent(platform)}/heartbeat`,
    ),
  ecosystem: () =>
    apiFetch<Record<string, unknown>>("/broker-connectivity/ecosystem"),
  compatibility: (broker?: string, symbol = TRADING_SYMBOL) =>
    apiFetch<Record<string, unknown>>(
      broker
        ? `/broker-connectivity/compatibility?broker=${encodeURIComponent(broker)}&symbol=${encodeURIComponent(resolveTradingSymbol(symbol))}`
        : `/broker-connectivity/compatibility?symbol=${encodeURIComponent(resolveTradingSymbol(symbol))}`,
    ),
  compatibilityDashboard: () =>
    apiFetch<Record<string, unknown>>(
      "/broker-connectivity/compatibility/dashboard",
    ),
  onboarding: (slug: string) =>
    apiFetch<Record<string, unknown>>(
      `/broker-connectivity/onboarding/${encodeURIComponent(slug)}`,
    ),
  certificationDashboard: () =>
    apiFetch<Record<string, unknown>>(
      "/broker-connectivity/certification/dashboard",
    ),
  certificationHistory: (broker?: string) =>
    apiFetch<Record<string, unknown>>(
      broker
        ? `/broker-connectivity/certification/history?broker=${encodeURIComponent(broker)}`
        : "/broker-connectivity/certification/history",
    ),
  runCertification: (body: Record<string, unknown> = {}) =>
    apiFetch<Record<string, unknown>>("/broker-connectivity/certification/run", {
      method: "POST",
      body,
    }),
};

export const gatewayManagerApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/gateway-manager/dashboard"),
  list: () => apiFetch<Record<string, unknown>>("/gateway-manager/gateways"),
  register: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/gateway-manager/gateways", {
      method: "POST",
      body,
    }),
  route: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/gateway-manager/route", {
      method: "POST",
      body,
    }),
  refreshHa: () =>
    apiFetch<Record<string, unknown>>("/gateway-manager/ha/refresh", {
      method: "POST",
      body: {},
    }),
};

export const weltradeApi = {
  profile: () => apiFetch<Record<string, unknown>>("/weltrade/profile"),
  health: () => apiFetch<Record<string, unknown>>("/weltrade/health"),
  dashboard: () => apiFetch<Record<string, unknown>>("/weltrade/dashboard"),
  connect: (body: {
    login: number;
    password?: string;
    server?: string;
    account_type?: "demo" | "live";
    prefer_attach?: boolean;
    path?: string;
    remember_on_gateway?: boolean;
  }) =>
    apiFetch<Record<string, unknown>>("/weltrade/connect", {
      method: "POST",
      body,
    }),
  attach: (body: { path?: string } = {}) =>
    apiFetch<Record<string, unknown>>("/weltrade/attach", {
      method: "POST",
      body,
    }),
  disconnect: () =>
    apiFetch<Record<string, unknown>>("/weltrade/disconnect", {
      method: "POST",
      body: {},
    }),
  reconnect: () =>
    apiFetch<Record<string, unknown>>("/weltrade/reconnect", {
      method: "POST",
      body: {},
    }),
};

export const opsApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/ops/dashboard"),
  metrics: () => apiFetch<Record<string, unknown>>("/ops/metrics"),
  alerts: () => apiFetch<Record<string, unknown>>("/ops/alerts"),
  audit: () => apiFetch<Record<string, unknown>>("/ops/audit"),
  rc1Telemetry: () => apiFetch<Record<string, unknown>>("/ops/rc1-telemetry"),
};

/** Institutional Operations Control Plane (Phase F) */
export const iteOpsApi = {
  controlCenter: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/control-center"),
  readiness: () => apiFetch<Record<string, unknown>>("/ite/ops/readiness"),
  setMode: (target: string, reason: string, confirmed: boolean) =>
    apiFetch<Record<string, unknown>>("/ite/ops/mode", {
      method: "POST",
      body: { target, reason, confirmed },
    }),
  armKill: (reason: string, confirmed: boolean) =>
    apiFetch<Record<string, unknown>>("/ite/ops/kill-switch/arm", {
      method: "POST",
      body: { reason, confirmed },
    }),
  disarmKill: (reason: string, confirmed: boolean) =>
    apiFetch<Record<string, unknown>>("/ite/ops/kill-switch/disarm", {
      method: "POST",
      body: { reason, confirmed },
    }),
  rollback: (target_config_version: string, reason: string, confirmed: boolean) =>
    apiFetch<Record<string, unknown>>("/ite/ops/rollback", {
      method: "POST",
      body: { target_config_version, reason, confirmed },
    }),
  alerts: (unacked_only = false) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/alerts?unacked_only=${unacked_only ? "true" : "false"}`,
    ),
  ackAlert: (alert_id: string) =>
    apiFetch<Record<string, unknown>>("/ite/ops/alerts/ack", {
      method: "POST",
      body: { alert_id },
    }),
  audit: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/ite/ops/audit?limit=${limit}`),
  configs: () => apiFetch<Record<string, unknown>>("/ite/ops/configs"),
  runbooks: () => apiFetch<Record<string, unknown>>("/ite/ops/runbooks"),
  executeRunbook: (runbook_id: string) =>
    apiFetch<Record<string, unknown>>(`/ite/ops/runbooks/${runbook_id}/execute`, {
      method: "POST",
      body: {},
    }),
  promote: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ite/ops/config/promote", {
      method: "POST",
      body,
    }),
  updateRisk: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ite/ops/risk", {
      method: "POST",
      body,
    }),
  autoTrading: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/auto-trading"),
  updateAutoTrading: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ite/ops/auto-trading", {
      method: "POST",
      body,
    }),
  evaluateAutoTrading: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ite/ops/auto-trading/evaluate", {
      method: "POST",
      body,
    }),
  emergencyStop: (reason: string, confirmed: boolean) =>
    apiFetch<Record<string, unknown>>("/ite/ops/auto-trading/emergency-stop", {
      method: "POST",
      body: { reason, confirmed },
    }),
  liveCertification: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/auto-trading/live-certification"),
  liveCertificationAttempt: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/ite/ops/auto-trading/live-certification/attempt",
      { method: "POST", body },
    ),
  liveCertificationReport: () =>
    apiFetch<Record<string, unknown>>(
      "/ite/ops/auto-trading/live-certification/report",
    ),
};

/** Institutional Market Intelligence Engine V1 — evaluate only */
export const marketIntelligenceApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/market-intelligence/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/market-intelligence/evaluate", {
      method: "POST",
      body,
    }),
};

/** Institutional AI Decision Engine V1 — dry-run evaluate, never order_send */
export const institutionalDecisionApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/institutional-decision/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/institutional-decision/evaluate", {
      method: "POST",
      body,
    }),
};

/** QuantForg AI Trading Robot V1 — evaluate only, never order_send */
export const aiRobotApi = {
  status: () => apiFetch<Record<string, unknown>>("/ai-robot/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ai-robot/evaluate", {
      method: "POST",
      body,
    }),
  selfAnalysis: (body: Record<string, unknown> = {}) =>
    apiFetch<Record<string, unknown>>("/ai-robot/self-analysis", {
      method: "POST",
      body,
    }),
};

/** Phase G — Production Reliability & Observability */
export const iteReliabilityApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/dashboard"),
  tick: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ite/reliability/tick", {
      method: "POST",
      body,
    }),
  heartbeat: (component: string, latency_ms = 0) =>
    apiFetch<Record<string, unknown>>("/ite/reliability/heartbeat", {
      method: "POST",
      body: { component, latency_ms },
    }),
  metrics: () => apiFetch<Record<string, unknown>>("/ite/reliability/metrics"),
  incidents: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/incidents"),
  timeline: (params?: Record<string, string>) => {
    const q = new URLSearchParams(params).toString();
    return apiFetch<Record<string, unknown>>(
      `/ite/reliability/timeline${q ? `?${q}` : ""}`,
    );
  },
  timelineExport: (fmt: "json" | "csv" = "json") =>
    apiFetch<Record<string, unknown>>(
      `/ite/reliability/timeline/export?fmt=${fmt}`,
    ),
  chaosInject: (failure: string) =>
    apiFetch<Record<string, unknown>>("/ite/reliability/chaos/inject", {
      method: "POST",
      body: { failure },
    }),
  chaosClear: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/chaos/clear", {
      method: "POST",
      body: {},
    }),
  recoverGateway: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/recovery/gateway", {
      method: "POST",
      body: {},
    }),
  recoverMt5: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/recovery/mt5", {
      method: "POST",
      body: {},
    }),
  recoverSafeRead: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/recovery/safe-read", {
      method: "POST",
      body: {},
    }),
  shadowReadiness: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/shadow/readiness"),
};

/** Phase H — Production Validation & Certification */
export const iteCertificationApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/ite/certification/dashboard"),
  run: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ite/certification/run", {
      method: "POST",
      body,
    }),
  report: () => apiFetch<Record<string, unknown>>("/ite/certification/report"),
  goNogo: () => apiFetch<Record<string, unknown>>("/ite/certification/go-nogo"),
  certificate: () =>
    apiFetch<Record<string, unknown>>("/ite/certification/certificate"),
  approve: (note = "") =>
    apiFetch<Record<string, unknown>>("/ite/certification/approve", {
      method: "POST",
      body: { note },
    }),
  checklist: () =>
    apiFetch<Record<string, unknown>>("/ite/certification/checklist"),
  canary: () => apiFetch<Record<string, unknown>>("/ite/certification/canary"),
  stress: () =>
    apiFetch<Record<string, unknown>>("/ite/certification/stress", {
      method: "POST",
      body: {},
    }),
  failures: () =>
    apiFetch<Record<string, unknown>>("/ite/certification/failures", {
      method: "POST",
      body: {},
    }),
};

export const decisionEngineApi = {
  dashboard: (symbol = TRADING_SYMBOL) =>
    apiFetch<Record<string, unknown>>(
      `/decision-engine/dashboard?symbol=${encodeURIComponent(resolveTradingSymbol(symbol))}`,
    ),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/decision-engine/evaluate", {
      method: "POST",
      body,
    }),
  paperPerformance: () =>
    apiFetch<Record<string, unknown>>("/decision-engine/paper/performance"),
  reports: () => apiFetch<Record<string, unknown>>("/decision-engine/reports"),
  paperOutcome: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/decision-engine/paper/outcome", {
      method: "POST",
      body,
    }),
};

export const quantStudioApi = {
  workspace: () => apiFetch<Record<string, unknown>>("/quant-studio/workspace"),
  blocks: () => apiFetch<Record<string, unknown>>("/quant-studio/blocks"),
  compile: (graph: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/quant-studio/builder/compile", {
      method: "POST",
      body: { graph },
    }),
  backtest: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/quant-studio/backtest", {
      method: "POST",
      body,
    }),
  walkforward: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/quant-studio/walkforward", {
      method: "POST",
      body,
    }),
  portfolioLab: () =>
    apiFetch<Record<string, unknown>>("/quant-studio/portfolio-lab"),
  liveMonitor: () =>
    apiFetch<Record<string, unknown>>("/quant-studio/live-monitor"),
  marketplace: () =>
    apiFetch<Record<string, unknown>>("/quant-studio/marketplace"),
  marketplaceSave: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/quant-studio/marketplace/save", {
      method: "POST",
      body,
    }),
  marketplaceAction: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/quant-studio/marketplace/action", {
      method: "POST",
      body,
    }),
};

/** Decision Intelligence Center — reject/hold gate; never force-execute */
export const decisionIntelligenceApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/decision-intelligence/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/decision-intelligence/evaluate", {
      method: "POST",
      body,
    }),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/decision-intelligence/history?limit=${limit}`,
    ),
  replay: (auditId: string) =>
    apiFetch<Record<string, unknown>>(
      `/decision-intelligence/replay?audit_id=${encodeURIComponent(auditId)}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>("/decision-intelligence/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/decision-intelligence/policies", {
      method: "POST",
      body,
    }),
};

/** Mission Control — executive dashboard (not Monitoring); live feeds only */
export const missionControlApi = {
  status: () => apiFetch<Record<string, unknown>>("/mission-control/status"),
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/mission-control/dashboard"),
  dashboardWithFeeds: (body: {
    capital?: Record<string, unknown> | null;
    positions?: Record<string, unknown>[] | null;
    xauusd?: Record<string, unknown> | null;
    daily?: Record<string, unknown> | null;
  }) =>
    apiFetch<Record<string, unknown>>("/mission-control/dashboard", {
      method: "POST",
      body,
    }),
  notes: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/mission-control/notes?limit=${limit}`),
  addNote: (body: { text: string; tags?: string[] }) =>
    apiFetch<Record<string, unknown>>("/mission-control/notes", {
      method: "POST",
      body,
    }),
  search: (q: string) =>
    apiFetch<Record<string, unknown>>(
      `/mission-control/search?q=${encodeURIComponent(q)}`,
    ),
};

/** Intelligence Platform — research/replay only; never order_send */
export const intelligencePlatformApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/intelligence-platform/status"),
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/intelligence-platform/dashboard"),
  dashboardWithFeeds: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/intelligence-platform/dashboard", {
      method: "POST",
      body,
    }),
  knowledge: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/intelligence-platform/knowledge?limit=${limit}`,
    ),
  addKnowledge: (body: { title: string; body: string; tags?: string[] }) =>
    apiFetch<Record<string, unknown>>("/intelligence-platform/knowledge", {
      method: "POST",
      body,
    }),
  searchKnowledge: (q: string) =>
    apiFetch<Record<string, unknown>>(
      `/intelligence-platform/knowledge/search?q=${encodeURIComponent(q)}`,
    ),
  replayLoad: (body: { strategy_key?: string; bars: Record<string, unknown>[] }) =>
    apiFetch<Record<string, unknown>>("/intelligence-platform/replay/load", {
      method: "POST",
      body,
    }),
  replayControl: (action: string) =>
    apiFetch<Record<string, unknown>>("/intelligence-platform/replay/control", {
      method: "POST",
      body: { action },
    }),
  decisionReplay: (auditId: string) =>
    apiFetch<Record<string, unknown>>(
      `/intelligence-platform/decision-replay?audit_id=${encodeURIComponent(auditId)}`,
    ),
};

/** Production Readiness Program — reliability desk; never order_send */
export const productionReadinessApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/production-readiness/status"),
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/production-readiness/dashboard"),
  dashboardWithFeeds: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/production-readiness/dashboard", {
      method: "POST",
      body,
    }),
  policies: () =>
    apiFetch<Record<string, unknown>>("/production-readiness/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/production-readiness/policies", {
      method: "POST",
      body,
    }),
  audit: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/production-readiness/audit?limit=${limit}`,
    ),
  logRecovery: (body: {
    action: string;
    ok?: boolean;
    detail?: string;
    meta?: Record<string, unknown>;
  }) =>
    apiFetch<Record<string, unknown>>("/production-readiness/audit/recovery", {
      method: "POST",
      body,
    }),
  logFailure: (body: {
    action: string;
    detail: string;
    meta?: Record<string, unknown>;
  }) =>
    apiFetch<Record<string, unknown>>("/production-readiness/audit/failure", {
      method: "POST",
      body,
    }),
};

/** Alpha Engine V1 — market quality scoring; never order_send */
export const alphaEngineApi = {
  status: () => apiFetch<Record<string, unknown>>("/alpha-engine/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/alpha-engine/evaluate", {
      method: "POST",
      body,
    }),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/alpha-engine/history?limit=${limit}`),
  replay: (auditId: string) =>
    apiFetch<Record<string, unknown>>(
      `/alpha-engine/replay?audit_id=${encodeURIComponent(auditId)}`,
    ),
  policies: () => apiFetch<Record<string, unknown>>("/alpha-engine/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/alpha-engine/policies", {
      method: "POST",
      body,
    }),
};

/** Trading Kernel V1 — orchestrates only; never order_send / never bypass Risk/Safety */
export const tradingKernelApi = {
  status: () => apiFetch<Record<string, unknown>>("/trading-kernel/status"),
  cycle: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/trading-kernel/cycle", {
      method: "POST",
      body,
    }),
  events: (limit = 100, traceId?: string) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (traceId) q.set("trace_id", traceId);
    return apiFetch<Record<string, unknown>>(`/trading-kernel/events?${q}`);
  },
  stageReplay: (traceId: string, stage?: string) => {
    const q = new URLSearchParams({ trace_id: traceId });
    if (stage) q.set("stage", stage);
    return apiFetch<Record<string, unknown>>(
      `/trading-kernel/replay/stage?${q}`,
    );
  },
  deterministicReplay: (traceId: string) =>
    apiFetch<Record<string, unknown>>(
      `/trading-kernel/replay/deterministic?trace_id=${encodeURIComponent(traceId)}`,
    ),
  policies: () => apiFetch<Record<string, unknown>>("/trading-kernel/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/trading-kernel/policies", {
      method: "POST",
      body,
    }),
  featureFlags: () =>
    apiFetch<Record<string, unknown>>("/trading-kernel/feature-flags"),
  setFeatureFlag: (flag: string, enabled: boolean) =>
    apiFetch<Record<string, unknown>>("/trading-kernel/feature-flags", {
      method: "POST",
      body: { flag, enabled },
    }),
  plugins: () => apiFetch<Record<string, unknown>>("/trading-kernel/plugins"),
  certification: () =>
    apiFetch<Record<string, unknown>>("/trading-kernel/certification"),
};

/** Multi-Agent AI — collaborate before approval; never order_send / never bypass */
export const multiAgentAiApi = {
  status: () => apiFetch<Record<string, unknown>>("/multi-agent-ai/status"),
  collaborate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/multi-agent-ai/collaborate", {
      method: "POST",
      body,
    }),
  events: (limit = 100, sessionId?: string) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (sessionId) q.set("session_id", sessionId);
    return apiFetch<Record<string, unknown>>(`/multi-agent-ai/events?${q}`);
  },
  memory: (limit = 50, kind?: string) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (kind) q.set("kind", kind);
    return apiFetch<Record<string, unknown>>(`/multi-agent-ai/memory?${q}`);
  },
  storeMemory: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/multi-agent-ai/memory", {
      method: "POST",
      body,
    }),
  governance: () =>
    apiFetch<Record<string, unknown>>("/multi-agent-ai/governance"),
  policies: () => apiFetch<Record<string, unknown>>("/multi-agent-ai/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/multi-agent-ai/policies", {
      method: "POST",
      body,
    }),
};

/** Institutional Trading Brain V3 — capital preservation; never order_send */
export const tradingBrainV3Api = {
  status: () => apiFetch<Record<string, unknown>>("/trading-brain-v3/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/trading-brain-v3/evaluate", {
      method: "POST",
      body,
    }),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/trading-brain-v3/history?limit=${limit}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>("/trading-brain-v3/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/trading-brain-v3/policies", {
      method: "POST",
      body,
    }),
};

/** Research & Validation Platform — pre-production only; never order_send */
export const researchValidationApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/research-validation/status"),
  registry: () =>
    apiFetch<Record<string, unknown>>("/research-validation/registry"),
  register: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/registry", {
      method: "POST",
      body,
    }),
  replayLoad: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/replay/load", {
      method: "POST",
      body,
    }),
  replayStep: () =>
    apiFetch<Record<string, unknown>>("/research-validation/replay/step", {
      method: "POST",
    }),
  walkForward: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/walk-forward", {
      method: "POST",
      body,
    }),
  paper: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/paper", {
      method: "POST",
      body,
    }),
  compare: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/compare", {
      method: "POST",
      body,
    }),
  certify: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/certify", {
      method: "POST",
      body,
    }),
  recordVersion: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/versions", {
      method: "POST",
      body,
    }),
  versions: (strategyKey?: string, limit = 50) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (strategyKey) q.set("strategy_key", strategyKey);
    return apiFetch<Record<string, unknown>>(
      `/research-validation/versions?${q}`,
    );
  },
  rollback: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/rollback", {
      method: "POST",
      body,
    }),
  rollbackAudit: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/research-validation/rollback/audit?limit=${limit}`,
    ),
  observatory: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/observatory", {
      method: "POST",
      body,
    }),
  release: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/release", {
      method: "POST",
      body,
    }),
  policies: () =>
    apiFetch<Record<string, unknown>>("/research-validation/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-validation/policies", {
      method: "POST",
      body,
    }),
};

/** Institutional XAUUSD Scalping AI V2 — advisory continuous loop; never order_send */
export const scalpingAiV2Api = {
  status: () => apiFetch<Record<string, unknown>>("/scalping-ai-v2/status"),
  cycle: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/scalping-ai-v2/cycle", {
      method: "POST",
      body,
    }),
  events: (limit = 100, cycleId?: string) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (cycleId) q.set("cycle_id", cycleId);
    return apiFetch<Record<string, unknown>>(`/scalping-ai-v2/events?${q}`);
  },
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/scalping-ai-v2/history?limit=${limit}`,
    ),
  policies: () => apiFetch<Record<string, unknown>>("/scalping-ai-v2/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/scalping-ai-v2/policies", {
      method: "POST",
      body,
    }),
  diagnostics: () =>
    apiFetch<Record<string, unknown>>("/scalping-ai-v2/diagnostics"),
  operator: () => apiFetch<Record<string, unknown>>("/scalping-ai-v2/operator"),
  audit: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/scalping-ai-v2/audit?limit=${limit}`,
    ),
  state: () => apiFetch<Record<string, unknown>>("/scalping-ai-v2/state"),
  emergencyStop: (reason = "operator") =>
    apiFetch<Record<string, unknown>>("/scalping-ai-v2/emergency-stop", {
      method: "POST",
      body: { reason },
    }),
  clearEmergencyStop: (reason = "operator_clear") =>
    apiFetch<Record<string, unknown>>(
      "/scalping-ai-v2/emergency-stop/clear",
      {
        method: "POST",
        body: { reason },
      },
    ),
  soak: (profile: "24h" | "48h" | "72h" | "stress" = "24h") =>
    apiFetch<Record<string, unknown>>("/scalping-ai-v2/soak", {
      method: "POST",
      body: { profile },
    }),
};

/** Adaptive Scalping Intelligence — advisory explainability; never order_send */
export const adaptiveScalpingIntelligenceApi = {
  status: () =>
    apiFetch<Record<string, unknown>>(
      "/adaptive-scalping-intelligence/status",
    ),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/adaptive-scalping-intelligence/evaluate",
      { method: "POST", body },
    ),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/adaptive-scalping-intelligence/history?limit=${limit}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>(
      "/adaptive-scalping-intelligence/policies",
    ),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/adaptive-scalping-intelligence/policies",
      { method: "POST", body },
    ),
};

/** Institutional Edge Engine — advisory edge analytics; never disables trading */
export const institutionalEdgeEngineApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/institutional-edge-engine/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/institutional-edge-engine/evaluate", {
      method: "POST",
      body,
    }),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/institutional-edge-engine/history?limit=${limit}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>("/institutional-edge-engine/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/institutional-edge-engine/policies", {
      method: "POST",
      body,
    }),
};

/** Alpha Factory — isolated research; never auto-promotes / never order_send */
export const alphaFactoryApi = {
  status: () => apiFetch<Record<string, unknown>>("/alpha-factory/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/alpha-factory/evaluate", {
      method: "POST",
      body,
    }),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/alpha-factory/history?limit=${limit}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>("/alpha-factory/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/alpha-factory/policies", {
      method: "POST",
      body,
    }),
};

/** Institutional Validation Program — read-only evidence; never order_send */
export const institutionalValidationProgramApi = {
  status: () =>
    apiFetch<Record<string, unknown>>(
      "/institutional-validation-program/status",
    ),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/institutional-validation-program/evaluate",
      {
        method: "POST",
        body,
      },
    ),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/institutional-validation-program/history?limit=${limit}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>(
      "/institutional-validation-program/policies",
    ),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/institutional-validation-program/policies",
      {
        method: "POST",
        body,
      },
    ),
};

/** Real Market Intelligence Platform — context only; never order_send */
export const realMarketIntelligencePlatformApi = {
  status: () =>
    apiFetch<Record<string, unknown>>(
      "/real-market-intelligence-platform/status",
    ),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/real-market-intelligence-platform/evaluate",
      {
        method: "POST",
        body,
      },
    ),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/real-market-intelligence-platform/history?limit=${limit}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>(
      "/real-market-intelligence-platform/policies",
    ),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/real-market-intelligence-platform/policies",
      {
        method: "POST",
        body,
      },
    ),
  currentContext: () =>
    apiFetch<Record<string, unknown>>(
      "/real-market-intelligence-platform/context/current",
    ),
  historicalContext: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/real-market-intelligence-platform/context/historical?limit=${limit}`,
    ),
};

/** Strategy Research Lab V1 — validation/promotion only, never order_send */
export const strategyLabApi = {
  status: () => apiFetch<Record<string, unknown>>("/strategy-lab/status"),
  registry: () => apiFetch<Record<string, unknown>>("/strategy-lab/registry"),
  compare: (runs: Record<string, unknown>[]) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/compare", {
      method: "POST",
      body: { runs },
    }),
  scorecard: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/scorecard", {
      method: "POST",
      body,
    }),
  validate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/validate", {
      method: "POST",
      body,
    }),
  replayLoad: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/replay/load", {
      method: "POST",
      body,
    }),
  replayControl: (action: string) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/replay/control", {
      method: "POST",
      body: { action },
    }),
  experimentCreate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/experiments", {
      method: "POST",
      body,
    }),
  experimentResults: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/experiments/results", {
      method: "POST",
      body,
    }),
  experimentList: (strategyKey?: string) => {
    const q = strategyKey
      ? `?strategy_key=${encodeURIComponent(strategyKey)}`
      : "";
    return apiFetch<Record<string, unknown>>(`/strategy-lab/experiments${q}`);
  },
  versionRecord: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/versions", {
      method: "POST",
      body,
    }),
  versions: (strategyKey: string) =>
    apiFetch<Record<string, unknown>>(
      `/strategy-lab/versions?strategy_key=${encodeURIComponent(strategyKey)}`,
    ),
  promotionOpen: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/promotion/open", {
      method: "POST",
      body,
    }),
  promotionApprove: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/strategy-lab/promotion/approve", {
      method: "POST",
      body,
    }),
  promotionDashboard: () =>
    apiFetch<Record<string, unknown>>("/strategy-lab/promotion/dashboard"),
};

export const researchLabApi = {
  dashboard: (symbol = TRADING_SYMBOL) =>
    apiFetch<Record<string, unknown>>(
      `/research-lab/dashboard?symbol=${encodeURIComponent(resolveTradingSymbol(symbol))}`,
    ),
  library: () => apiFetch<Record<string, unknown>>("/research-lab/library"),
  validate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-lab/validate", {
      method: "POST",
      body,
    }),
  compare: () => apiFetch<Record<string, unknown>>("/research-lab/compare"),
  regime: (symbol = TRADING_SYMBOL) =>
    apiFetch<Record<string, unknown>>(
      `/research-lab/regime?symbol=${encodeURIComponent(resolveTradingSymbol(symbol))}`,
    ),
  parameters: () => apiFetch<Record<string, unknown>>("/research-lab/parameters"),
  setParameters: (overrides: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-lab/parameters", {
      method: "POST",
      body: { overrides },
    }),
  paper: () => apiFetch<Record<string, unknown>>("/research-lab/paper"),
  promotionCriteria: () =>
    apiFetch<Record<string, unknown>>("/research-lab/promotion/criteria"),
  setPromotionCriteria: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-lab/promotion/criteria", {
      method: "POST",
      body,
    }),
  promote: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/research-lab/promotion/evaluate", {
      method: "POST",
      body,
    }),
  report: (strategyKey?: string) => {
    const q = strategyKey
      ? `?strategy_key=${encodeURIComponent(strategyKey)}`
      : "";
    return apiFetch<Record<string, unknown>>(`/research-lab/report${q}`);
  },
};

export const ecosystemApi = {
  hub: () => apiFetch<Record<string, unknown>>("/ecosystem/hub"),
  journal: (q = "", tag?: string) => {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (tag) params.set("tag", tag);
    const qs = params.toString();
    return apiFetch<Record<string, unknown>>(
      `/ecosystem/journal${qs ? `?${qs}` : ""}`,
    );
  },
  journalSave: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ecosystem/journal", {
      method: "POST",
      body,
    }),
  journalIngestPaper: () =>
    apiFetch<Record<string, unknown>>("/ecosystem/journal/ingest-paper", {
      method: "POST",
      body: {},
    }),
  playbooks: () => apiFetch<Record<string, unknown>>("/ecosystem/playbooks"),
  playbookSave: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ecosystem/playbooks", {
      method: "POST",
      body,
    }),
  coach: () => apiFetch<Record<string, unknown>>("/ecosystem/coach"),
  watchlists: () => apiFetch<Record<string, unknown>>("/ecosystem/watchlists"),
  watchlistSave: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ecosystem/watchlists", {
      method: "POST",
      body,
    }),
  workspaces: () => apiFetch<Record<string, unknown>>("/ecosystem/workspaces"),
  workspaceSave: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ecosystem/workspaces", {
      method: "POST",
      body,
    }),
  alerts: () => apiFetch<Record<string, unknown>>("/ecosystem/alerts"),
  alertCreate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ecosystem/alerts", {
      method: "POST",
      body,
    }),
  learning: () => apiFetch<Record<string, unknown>>("/ecosystem/learning"),
  learningComplete: (lessonId: string) =>
    apiFetch<Record<string, unknown>>("/ecosystem/learning/complete", {
      method: "POST",
      body: { lesson_id: lessonId },
    }),
  reports: (period = "weekly") =>
    apiFetch<Record<string, unknown>>(
      `/ecosystem/reports?period=${encodeURIComponent(period)}`,
    ),
  preferences: () =>
    apiFetch<Record<string, unknown>>("/ecosystem/preferences"),
  preferencesSave: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ecosystem/preferences", {
      method: "POST",
      body,
    }),
  syncStatus: () =>
    apiFetch<Record<string, unknown>>("/ecosystem/sync/status"),
  syncExport: () =>
    apiFetch<Record<string, unknown>>("/ecosystem/sync/export", {
      method: "POST",
      body: {},
    }),
  syncImport: (bundle: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/ecosystem/sync/import", {
      method: "POST",
      body: { bundle },
    }),
};

export const quantAiApi = {
  dashboard: (symbol?: string, forceRefresh = false) => {
    const params = new URLSearchParams();
    params.set("symbol", resolveTradingSymbol(symbol));
    if (forceRefresh) params.set("force_refresh", "true");
    const q = params.toString();
    return apiFetch<Record<string, unknown>>(
      `/quant-ai/dashboard${q ? `?${q}` : ""}`,
    );
  },
  symbol: (symbol: string) =>
    apiFetch<Record<string, unknown>>(
      `/quant-ai/symbol/${encodeURIComponent(resolveTradingSymbol(symbol))}`,
    ),
  portfolio: () => apiFetch<Record<string, unknown>>("/quant-ai/portfolio"),
  risk: () => apiFetch<Record<string, unknown>>("/quant-ai/risk"),
  execution: () => apiFetch<Record<string, unknown>>("/quant-ai/execution"),
  tradeReview: (trade: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/quant-ai/trade-review", {
      method: "POST",
      body: { trade },
    }),
};

export const intelligenceApi = {
  dashboard: (market_code = "XAU", symbol?: string) =>
    apiFetch<Record<string, unknown>>(
      `/intelligence/dashboard?market_code=${encodeURIComponent(market_code)}${
        `&symbol=${encodeURIComponent(resolveTradingSymbol(symbol))}`
      }`,
    ),
  marketContext: (market_code = "XAU", symbol?: string) =>
    apiFetch<Record<string, unknown>>(
      `/intelligence/market-context?market_code=${encodeURIComponent(market_code)}${
        `&symbol=${encodeURIComponent(resolveTradingSymbol(symbol))}`
      }`,
    ),
  news: (limit = 20) =>
    apiFetch<unknown[]>(`/intelligence/news?limit=${limit}`),
  calendar: (limit = 20) =>
    apiFetch<unknown[]>(`/intelligence/calendar?limit=${limit}`),
  analysis: (market_code = "FX", symbol?: string) =>
    apiFetch<Record<string, unknown>>(
      `/intelligence/analysis?market_code=${encodeURIComponent(market_code)}${
        symbol ? `&symbol=${encodeURIComponent(symbol)}` : ""
      }`,
    ),
  events: (limit = 30) =>
    apiFetch<unknown[]>(`/intelligence/events?limit=${limit}`),
  providers: () => apiFetch<unknown[]>(`/intelligence/providers`),
  status: () => apiFetch<Record<string, unknown>>(`/intelligence/status`),
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
