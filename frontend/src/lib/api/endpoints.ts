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
  optimization: (limit = 200) =>
    apiFetch<Record<string, unknown>>(
      `/execution/optimization?limit=${limit}`,
    ),
  audits: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/execution/audits?limit=${limit}`),
  auditsByRequest: (requestId: string) =>
    apiFetch<Record<string, unknown>>(
      `/execution/audits/by-request/${encodeURIComponent(requestId)}`,
    ),
};

/** Institutional Performance Intelligence — journals only; advisory. */
export const performanceIntelligenceApi = {
  dashboard: (limit = 200, period = "monthly") =>
    apiFetch<Record<string, unknown>>(
      `/performance-intelligence/dashboard?limit=${limit}&period=${encodeURIComponent(period)}`,
    ),
  sessions: (limit = 200) =>
    apiFetch<Record<string, unknown>>(
      `/performance-intelligence/sessions?limit=${limit}`,
    ),
  regimes: (limit = 200) =>
    apiFetch<Record<string, unknown>>(
      `/performance-intelligence/regimes?limit=${limit}`,
    ),
  signals: (limit = 200) =>
    apiFetch<Record<string, unknown>>(
      `/performance-intelligence/signals?limit=${limit}`,
    ),
  noTrade: () =>
    apiFetch<Record<string, unknown>>("/performance-intelligence/no-trade"),
  time: (limit = 200) =>
    apiFetch<Record<string, unknown>>(
      `/performance-intelligence/time?limit=${limit}`,
    ),
  reports: (period = "monthly", limit = 200) =>
    apiFetch<Record<string, unknown>>(
      `/performance-intelligence/reports?period=${encodeURIComponent(period)}&limit=${limit}`,
    ),
};

export const replayEvidenceLabApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/replay-evidence-lab/dashboard"),
  confidence: () =>
    apiFetch<Record<string, unknown>>("/replay-evidence-lab/confidence"),
  gates: () => apiFetch<Record<string, unknown>>("/replay-evidence-lab/gates"),
  counterfactual: () =>
    apiFetch<Record<string, unknown>>("/replay-evidence-lab/counterfactual"),
  reports: () =>
    apiFetch<Record<string, unknown>>("/replay-evidence-lab/reports"),
  evidence: (lane: "live" | "demo" | "replay" | "research", limit = 200) =>
    apiFetch<Record<string, unknown>>(
      `/replay-evidence-lab/evidence/${lane}?limit=${limit}`,
    ),
  replay: (payload: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/replay-evidence-lab/replay", {
      method: "POST",
      body: payload,
    }),
};

export const tradingOperationsCenterApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/trading-operations-center/dashboard"),
  brief: () =>
    apiFetch<Record<string, unknown>>("/trading-operations-center/brief"),
  checklist: () =>
    apiFetch<Record<string, unknown>>("/trading-operations-center/checklist"),
  endOfDay: () =>
    apiFetch<Record<string, unknown>>("/trading-operations-center/end-of-day"),
  weekly: () =>
    apiFetch<Record<string, unknown>>("/trading-operations-center/weekly"),
  monthly: () =>
    apiFetch<Record<string, unknown>>("/trading-operations-center/monthly"),
  alerts: () =>
    apiFetch<Record<string, unknown>>("/trading-operations-center/alerts"),
  analyze: (payload: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/trading-operations-center/analyze", {
      method: "POST",
      body: payload,
    }),
};

export const auditGovernanceApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/audit-governance/dashboard"),
  events: (params?: {
    limit?: number;
    category?: string;
    severity?: string;
    q?: string;
    since?: string;
    until?: string;
  }) => {
    const sp = new URLSearchParams();
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.category) sp.set("category", params.category);
    if (params?.severity) sp.set("severity", params.severity);
    if (params?.q) sp.set("q", params.q);
    if (params?.since) sp.set("since", params.since);
    if (params?.until) sp.set("until", params.until);
    const qs = sp.toString();
    return apiFetch<Record<string, unknown>>(
      `/audit-governance/events${qs ? `?${qs}` : ""}`,
    );
  },
  timeline: (limit = 100) =>
    apiFetch<Record<string, unknown>>(
      `/audit-governance/timeline?limit=${limit}`,
    ),
  changeHistory: () =>
    apiFetch<Record<string, unknown>>("/audit-governance/change-history"),
  tradeVersions: (tradeId?: string) =>
    apiFetch<Record<string, unknown>>(
      tradeId
        ? `/audit-governance/trade-versions?trade_id=${encodeURIComponent(tradeId)}`
        : "/audit-governance/trade-versions",
    ),
  accountability: () =>
    apiFetch<Record<string, unknown>>("/audit-governance/accountability"),
  security: () =>
    apiFetch<Record<string, unknown>>("/audit-governance/security"),
  reports: () =>
    apiFetch<Record<string, unknown>>("/audit-governance/reports"),
  exportUrl: "/audit-governance/export",
};

export const institutionalDataWarehouseApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/institutional-data-warehouse/dashboard"),
  datasets: () =>
    apiFetch<Record<string, unknown>>("/institutional-data-warehouse/datasets"),
  dataset: (
    domain: string,
    params?: {
      limit?: number;
      q?: string;
      since?: string;
      until?: string;
      session?: string;
      environment?: string;
      strategy_version?: string;
    },
  ) => {
    const sp = new URLSearchParams();
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.q) sp.set("q", params.q);
    if (params?.since) sp.set("since", params.since);
    if (params?.until) sp.set("until", params.until);
    if (params?.session) sp.set("session", params.session);
    if (params?.environment) sp.set("environment", params.environment);
    if (params?.strategy_version) {
      sp.set("strategy_version", params.strategy_version);
    }
    const qs = sp.toString();
    return apiFetch<Record<string, unknown>>(
      `/institutional-data-warehouse/datasets/${encodeURIComponent(domain)}${qs ? `?${qs}` : ""}`,
    );
  },
  analytics: () =>
    apiFetch<Record<string, unknown>>("/institutional-data-warehouse/analytics"),
  reports: () =>
    apiFetch<Record<string, unknown>>("/institutional-data-warehouse/reports"),
  dimensional: () =>
    apiFetch<Record<string, unknown>>("/institutional-data-warehouse/dimensional"),
  quality: () =>
    apiFetch<Record<string, unknown>>("/institutional-data-warehouse/quality"),
  retention: (apply = false) =>
    apiFetch<Record<string, unknown>>(
      `/institutional-data-warehouse/retention?apply=${apply ? "true" : "false"}`,
    ),
  aggregate: (domain = "trades", grain = "day") =>
    apiFetch<Record<string, unknown>>(
      `/institutional-data-warehouse/query/aggregate?domain=${encodeURIComponent(domain)}&grain=${encodeURIComponent(grain)}`,
    ),
  rolling: (domain = "trades", window = 20) =>
    apiFetch<Record<string, unknown>>(
      `/institutional-data-warehouse/query/rolling?domain=${encodeURIComponent(domain)}&window=${window}`,
    ),
  snapshot: () =>
    apiFetch<Record<string, unknown>>("/institutional-data-warehouse/snapshot", {
      method: "POST",
      body: {},
    }),
};

export const institutionalObservabilityApi = {
  dashboard: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/dashboard"),
  health: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/health"),
  latency: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/latency"),
  resources: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/resources"),
  errors: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/errors"),
  uptime: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/uptime"),
  dependency: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/dependency"),
  alerts: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/alerts"),
  reports: () =>
    apiFetch<Record<string, unknown>>("/institutional-observability/reports"),
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
  servicesHealth: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/services-health"),
  setMode: (target: string, reason: string, confirmed: boolean) =>
    apiFetch<Record<string, unknown>>("/ite/ops/mode", {
      method: "POST",
      body: { target, reason, confirmed },
    }),
  launchReadiness: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/launch-readiness"),
  promoteLaunch: (body: {
    reason: string;
    confirmed: boolean;
    activate_auto_trading?: boolean;
  }) =>
    apiFetch<Record<string, unknown>>("/ite/ops/launch-readiness/promote", {
      method: "POST",
      body,
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
  strategyDiagnostics: (limit = 100) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/strategy-diagnostics?limit=${limit}`,
    ),
  liveExecutionExplain: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/live-execution-explain?limit=${limit}`,
    ),
  adaptiveOpportunity: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/adaptive-opportunity?limit=${limit}`,
    ),
  adaptiveOpportunityTimeline: (limit = 100) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/adaptive-opportunity-timeline?limit=${limit}`,
    ),
  strategyIntelligenceCenter: (days = 90) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/strategy-intelligence-center?days=${days}`,
    ),
  marketRegimeIntelligence: (limit = 100) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/market-regime-intelligence?limit=${limit}`,
    ),
  portfolioAnalytics: (days = 365, strategyId = "production") =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/portfolio-analytics?days=${days}&strategy_id=${encodeURIComponent(strategyId)}`,
    ),
  portfolioAnalyticsReport: (period: string, days = 365) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/portfolio-analytics/reports/${period}?days=${days}`,
    ),
  productionReadinessReview: (writeReport = false) =>
    apiFetch<Record<string, unknown>>(
      `/ite/ops/production-readiness-review?write_report=${writeReport ? "true" : "false"}`,
    ),
  productionReadinessReviewChecklist: () =>
    apiFetch<Record<string, unknown>>(
      "/ite/ops/production-readiness-review/checklist",
    ),
  productionReadinessReviewRisks: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/production-readiness-review/risks"),
  productionReadinessReviewExecutive: () =>
    apiFetch<Record<string, unknown>>(
      "/ite/ops/production-readiness-review/executive",
    ),
  institutionalControlCenter: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/institutional-control-center"),
  institutionalControlCenterKpis: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/institutional-control-center/kpis"),
  institutionalControlCenterAlerts: () =>
    apiFetch<Record<string, unknown>>(
      "/ite/ops/institutional-control-center/alerts",
    ),
  institutionalControlCenterTimeline: () =>
    apiFetch<Record<string, unknown>>(
      "/ite/ops/institutional-control-center/timeline",
    ),
  thresholdPromotion: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/threshold-promotion"),
  thresholdPromote: (body: {
    reason: string;
    confirmed: boolean;
    evidence_reference?: string;
  }) =>
    apiFetch<Record<string, unknown>>("/ite/ops/threshold-promotion/promote", {
      method: "POST",
      body,
    }),
  thresholdRollback: (body: { reason: string; confirmed: boolean }) =>
    apiFetch<Record<string, unknown>>("/ite/ops/threshold-promotion/rollback", {
      method: "POST",
      body,
    }),
  experimentalThreshold: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/experimental-threshold"),
  experimentalActivate: (body: { reason: string; confirmed: boolean }) =>
    apiFetch<Record<string, unknown>>("/ite/ops/experimental-threshold/activate", {
      method: "POST",
      body,
    }),
  experimentalRollback: (body: { reason: string; confirmed: boolean }) =>
    apiFetch<Record<string, unknown>>(
      "/ite/ops/experimental-threshold/rollback",
      { method: "POST", body },
    ),
  experimentalReport: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/experimental-threshold/report"),
  witnessHealth: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/witness-health"),
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
  executeNow: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/auto-trading/execute-now", {
      method: "POST",
    }),
  institutionalAlpha: () =>
    apiFetch<Record<string, unknown>>("/ite/ops/institutional-alpha"),
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
  productionHardening: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/production-hardening"),
  aiValidation: (replayDay?: string) => {
    const q = replayDay ? `?replay_day=${encodeURIComponent(replayDay)}` : "";
    return apiFetch<Record<string, unknown>>(
      `/ite/reliability/ai-validation${q}`,
    );
  },
  performanceLab: (params?: {
    symbol?: string;
    session?: string;
    regime?: string;
    replayId?: string;
    frameIndex?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.symbol) sp.set("symbol", params.symbol);
    if (params?.session) sp.set("session", params.session);
    if (params?.regime) sp.set("regime", params.regime);
    if (params?.replayId) sp.set("replay_id", params.replayId);
    if (params?.frameIndex != null) sp.set("frame_index", String(params.frameIndex));
    const q = sp.toString();
    return apiFetch<Record<string, unknown>>(
      `/ite/reliability/performance-lab${q ? `?${q}` : ""}`,
    );
  },
  network: () =>
    apiFetch<Record<string, unknown>>("/ite/reliability/network"),
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

/** Production Replay & Validation — simulation-only walk-forward; never order_send */
export const productionReplayApi = {
  status: () => apiFetch<Record<string, unknown>>("/production-replay/status"),
  run: (body: { days?: number; max_evaluations?: number } = {}) =>
    apiFetch<Record<string, unknown>>("/production-replay/run", {
      method: "POST",
      body,
    }),
  report: () => apiFetch<Record<string, unknown>>("/production-replay/report"),
};

/** Threshold Performance Analysis — offline research; never mutates live gates */
export const thresholdPerformanceApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/threshold-performance-analysis/status"),
  run: (body: { days?: number; max_evaluations?: number } = {}) =>
    apiFetch<Record<string, unknown>>("/threshold-performance-analysis/run", {
      method: "POST",
      body,
    }),
  report: () =>
    apiFetch<Record<string, unknown>>("/threshold-performance-analysis/report"),
};

/** Candidate Validation — production 80/80 vs candidate 70/75; never mutates production */
export const candidateValidationApi = {
  status: () => apiFetch<Record<string, unknown>>("/candidate-validation/status"),
  run: (body: { days?: number; max_evaluations?: number } = {}) =>
    apiFetch<Record<string, unknown>>("/candidate-validation/run", {
      method: "POST",
      body,
    }),
  report: () => apiFetch<Record<string, unknown>>("/candidate-validation/report"),
};

/** Micro Account Analyzer — feasibility only; never mutates Institutional Mode */
export const microAccountAnalyzerApi = {
  profiles: () =>
    apiFetch<Record<string, unknown>>("/micro-account-analyzer/profiles"),
  analyze: (body: {
    balance?: string;
    risk_pct?: string;
    atr?: string | null;
    use_live_broker?: boolean;
    use_live_atr?: boolean;
  } = {}) =>
    apiFetch<Record<string, unknown>>("/micro-account-analyzer/analyze", {
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

/** Live Learning Program — evidence only; never order_send / never auto-tune */
export const liveLearningProgramApi = {
  status: () =>
    apiFetch<Record<string, unknown>>("/live-learning-program/status"),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/live-learning-program/evaluate", {
      method: "POST",
      body,
    }),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/live-learning-program/history?limit=${limit}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>("/live-learning-program/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/live-learning-program/policies", {
      method: "POST",
      body,
    }),
};

/** Production Readiness Certification — certify only; never order_send */
export const productionReadinessCertificationApi = {
  status: () =>
    apiFetch<Record<string, unknown>>(
      "/production-readiness-certification/status",
    ),
  evaluate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/production-readiness-certification/evaluate",
      {
        method: "POST",
        body,
      },
    ),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/production-readiness-certification/history?limit=${limit}`,
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>(
      "/production-readiness-certification/policies",
    ),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      "/production-readiness-certification/policies",
      {
        method: "POST",
        body,
      },
    ),
};

/** Integration Sprint V1 — read-only feeds + data bus; never order_send */
export const integrationSprintV1Api = {
  status: () =>
    apiFetch<Record<string, unknown>>("/integration-sprint-v1/status"),
  bus: () => apiFetch<Record<string, unknown>>("/integration-sprint-v1/bus"),
  feed: (name: string) =>
    apiFetch<Record<string, unknown>>(
      `/integration-sprint-v1/feeds/${encodeURIComponent(name)}`,
    ),
  hydrate: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/integration-sprint-v1/hydrate", {
      method: "POST",
      body,
    }),
  storageList: (namespace: string, limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/integration-sprint-v1/storage/${encodeURIComponent(namespace)}?limit=${limit}`,
    ),
  storageAppend: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/integration-sprint-v1/storage/append", {
      method: "POST",
      body,
    }),
  warehouseIngest: (bars: Record<string, unknown>[]) =>
    apiFetch<Record<string, unknown>>(
      "/integration-sprint-v1/warehouse/ingest",
      {
        method: "POST",
        body: { bars },
      },
    ),
  policies: () =>
    apiFetch<Record<string, unknown>>("/integration-sprint-v1/policies"),
  updatePolicies: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/integration-sprint-v1/policies", {
      method: "POST",
      body,
    }),
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

/** AI Quant Scientist — advisory research only; never modifies production */
export const aqsApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/aqs/dashboard"),
  feed: () => apiFetch<Record<string, unknown>>("/aqs/feed"),
  recommendations: (status?: string, limit = 100) => {
    const sp = new URLSearchParams();
    sp.set("limit", String(limit));
    if (status) sp.set("status", status);
    return apiFetch<Record<string, unknown>>(`/aqs/recommendations?${sp}`);
  },
  recommendation: (id: string) =>
    apiFetch<Record<string, unknown>>(
      `/aqs/recommendations/${encodeURIComponent(id)}`,
    ),
  setStatus: (id: string, status: string) =>
    apiFetch<Record<string, unknown>>(
      `/aqs/recommendations/${encodeURIComponent(id)}/status`,
      { method: "POST", body: { status } },
    ),
  patterns: () => apiFetch<Record<string, unknown>>("/aqs/patterns"),
  compare: () => apiFetch<Record<string, unknown>>("/aqs/compare"),
  regimes: () => apiFetch<Record<string, unknown>>("/aqs/regimes"),
  sensitivity: () => apiFetch<Record<string, unknown>>("/aqs/sensitivity"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/aqs/reports?limit=${limit}`),
  ask: (q: string) =>
    apiFetch<Record<string, unknown>>(
      `/aqs/ask?q=${encodeURIComponent(q)}`,
    ),
};

/** AI Quant Copilot — operational explanations only (never modifies production) */
export const aqcApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/aqc/dashboard"),
  ask: (q: string) =>
    apiFetch<Record<string, unknown>>(
      `/aqc/ask?q=${encodeURIComponent(q)}`,
    ),
  investigations: (limit = 40) =>
    apiFetch<Record<string, unknown>>(`/aqc/investigations?limit=${limit}`),
  investigation: (id: string) =>
    apiFetch<Record<string, unknown>>(
      `/aqc/investigations/${encodeURIComponent(id)}`,
    ),
  timeline: () => apiFetch<Record<string, unknown>>("/aqc/timeline"),
  comparison: () => apiFetch<Record<string, unknown>>("/aqc/comparison"),
  evidence: () => apiFetch<Record<string, unknown>>("/aqc/evidence"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/aqc/reports?limit=${limit}`),
  recommendations: (opts?: {
    status?: string;
    minConfidence?: number;
    researchArea?: string;
    limit?: number;
  }) => {
    const sp = new URLSearchParams();
    sp.set("limit", String(opts?.limit ?? 50));
    if (opts?.status) sp.set("status", opts.status);
    if (opts?.minConfidence != null)
      sp.set("min_confidence", String(opts.minConfidence));
    if (opts?.researchArea) sp.set("research_area", opts.researchArea);
    return apiFetch<Record<string, unknown>>(`/aqc/recommendations?${sp}`);
  },
  conversations: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/aqc/conversations?limit=${limit}`),
  correlations: () => apiFetch<Record<string, unknown>>("/aqc/correlations"),
};

/** Execution Quality Suite — read-only execution intelligence */
export const eqsApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/eqs/dashboard"),
  latency: () => apiFetch<Record<string, unknown>>("/eqs/latency"),
  slippage: () => apiFetch<Record<string, unknown>>("/eqs/slippage"),
  timelines: (limit = 40) =>
    apiFetch<Record<string, unknown>>(`/eqs/timelines?limit=${limit}`),
  fillQuality: () => apiFetch<Record<string, unknown>>("/eqs/fill-quality"),
  consistency: () => apiFetch<Record<string, unknown>>("/eqs/consistency"),
  brokerHealth: () => apiFetch<Record<string, unknown>>("/eqs/broker-health"),
  score: () => apiFetch<Record<string, unknown>>("/eqs/score"),
  alerts: () => apiFetch<Record<string, unknown>>("/eqs/alerts"),
  evidence: () => apiFetch<Record<string, unknown>>("/eqs/evidence"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/eqs/reports?limit=${limit}`),
};

/** Reliability Engineering Suite — read-only platform reliability */
export const resApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/res/dashboard"),
  health: () => apiFetch<Record<string, unknown>>("/res/health"),
  services: () => apiFetch<Record<string, unknown>>("/res/services"),
  availability: () => apiFetch<Record<string, unknown>>("/res/availability"),
  recovery: () => apiFetch<Record<string, unknown>>("/res/recovery"),
  failures: () => apiFetch<Record<string, unknown>>("/res/failures"),
  trends: () => apiFetch<Record<string, unknown>>("/res/trends"),
  score: () => apiFetch<Record<string, unknown>>("/res/score"),
  evidence: () => apiFetch<Record<string, unknown>>("/res/evidence"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/res/reports?limit=${limit}`),
};

/** Continuous Validation Framework — read-only evidence / never promotes */
export const cvfApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/cvf/dashboard"),
  replayVsLive: () => apiFetch<Record<string, unknown>>("/cvf/replay-vs-live"),
  drift: () => apiFetch<Record<string, unknown>>("/cvf/drift"),
  regimes: () => apiFetch<Record<string, unknown>>("/cvf/regimes"),
  parameters: () => apiFetch<Record<string, unknown>>("/cvf/parameters"),
  confidence: () => apiFetch<Record<string, unknown>>("/cvf/confidence"),
  alerts: () => apiFetch<Record<string, unknown>>("/cvf/alerts"),
  evidence: () => apiFetch<Record<string, unknown>>("/cvf/evidence"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/cvf/reports?limit=${limit}`),
};

/** Institutional Simulation Engine — isolated digital twin */
export const iseApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/ise/dashboard"),
  catalog: () => apiFetch<Record<string, unknown>>("/ise/catalog"),
  simulate: (mode: string, scenario?: string, paths = 100) => {
    const sp = new URLSearchParams();
    sp.set("mode", mode);
    sp.set("paths", String(paths));
    if (scenario) sp.set("scenario", scenario);
    return apiFetch<Record<string, unknown>>(`/ise/simulate?${sp}`);
  },
  simulations: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/ise/simulations?limit=${limit}`),
  simulation: (id: string) =>
    apiFetch<Record<string, unknown>>(
      `/ise/simulations/${encodeURIComponent(id)}`,
    ),
  aqsAnalysis: (id: string) =>
    apiFetch<Record<string, unknown>>(
      `/ise/simulations/${encodeURIComponent(id)}/aqs`,
    ),
  monteCarlo: (paths = 100, scenario?: string) => {
    const sp = new URLSearchParams();
    sp.set("paths", String(paths));
    if (scenario) sp.set("scenario", scenario);
    return apiFetch<Record<string, unknown>>(`/ise/monte-carlo?${sp}`);
  },
  walkForward: () => apiFetch<Record<string, unknown>>("/ise/walk-forward"),
  stress: (stress = "volatility_spike") =>
    apiFetch<Record<string, unknown>>(
      `/ise/stress?stress=${encodeURIComponent(stress)}`,
    ),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/ise/reports?limit=${limit}`),
  knowledgeNodes: (limit = 40) =>
    apiFetch<Record<string, unknown>>(
      `/ise/knowledge-nodes?limit=${limit}`,
    ),
};

/** Institutional Release & Deployment — human approval governance */
export const irdpApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/irdp/dashboard"),
  releases: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/irdp/releases?limit=${limit}`),
  release: (id: string) =>
    apiFetch<Record<string, unknown>>(
      `/irdp/releases/${encodeURIComponent(id)}`,
    ),
  createRelease: (body: {
    version: string;
    component?: string;
    notes?: string;
  }) =>
    apiFetch<Record<string, unknown>>("/irdp/releases", {
      method: "POST",
      body,
    }),
  advance: (id: string, toStage?: string) =>
    apiFetch<Record<string, unknown>>(
      `/irdp/releases/${encodeURIComponent(id)}/advance`,
      { method: "POST", body: { to_stage: toStage ?? null } },
    ),
  approve: (
    id: string,
    body: { approver: string; decision: string; comment?: string },
  ) =>
    apiFetch<Record<string, unknown>>(
      `/irdp/releases/${encodeURIComponent(id)}/approve`,
      { method: "POST", body },
    ),
  rollbackPlan: (
    id: string,
    body: { requested_by: string; reason?: string },
  ) =>
    apiFetch<Record<string, unknown>>(
      `/irdp/releases/${encodeURIComponent(id)}/rollback-plan`,
      { method: "POST", body },
    ),
  checklist: () => apiFetch<Record<string, unknown>>("/irdp/checklist"),
  monitoring: () => apiFetch<Record<string, unknown>>("/irdp/monitoring"),
  approvals: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/irdp/approvals?limit=${limit}`),
  rollbacks: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/irdp/rollbacks?limit=${limit}`),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/irdp/reports?limit=${limit}`),
  audit: (id: string) =>
    apiFetch<Record<string, unknown>>(
      `/irdp/releases/${encodeURIComponent(id)}/audit`,
    ),
};

/** Institutional Risk Analytics Platform — read-only portfolio risk intelligence */
export const irapApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/irap/dashboard"),
  metrics: () => apiFetch<Record<string, unknown>>("/irap/metrics"),
  exposure: () => apiFetch<Record<string, unknown>>("/irap/exposure"),
  drawdown: () => apiFetch<Record<string, unknown>>("/irap/drawdown"),
  correlation: () => apiFetch<Record<string, unknown>>("/irap/correlation"),
  stress: () => apiFetch<Record<string, unknown>>("/irap/stress"),
  alerts: () => apiFetch<Record<string, unknown>>("/irap/alerts"),
  trends: () => apiFetch<Record<string, unknown>>("/irap/trends"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/irap/reports?limit=${limit}`),
};

/** Institutional Strategy Lifecycle Manager — governance layer (human approval only) */
export const islmApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/islm/dashboard"),
  registry: (limit = 100) =>
    apiFetch<Record<string, unknown>>(`/islm/registry?limit=${limit}`),
  strategy: (strategyId: string) =>
    apiFetch<Record<string, unknown>>(
      `/islm/strategies/${encodeURIComponent(strategyId)}`,
    ),
  timeline: (strategyId?: string) =>
    apiFetch<Record<string, unknown>>(
      strategyId
        ? `/islm/timeline?strategy_id=${encodeURIComponent(strategyId)}`
        : "/islm/timeline",
    ),
  versions: (strategyId?: string) =>
    apiFetch<Record<string, unknown>>(
      strategyId
        ? `/islm/versions?strategy_id=${encodeURIComponent(strategyId)}`
        : "/islm/versions",
    ),
  health: () => apiFetch<Record<string, unknown>>("/islm/health"),
  evidence: (strategyId?: string) =>
    apiFetch<Record<string, unknown>>(
      strategyId
        ? `/islm/evidence?strategy_id=${encodeURIComponent(strategyId)}`
        : "/islm/evidence",
    ),
  alerts: () => apiFetch<Record<string, unknown>>("/islm/alerts"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/islm/reports?limit=${limit}`),
  approvals: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/islm/approvals?limit=${limit}`),
  approve: (body: {
    strategy_id: string;
    to_state: string;
    decision: "approved" | "rejected";
    comment?: string;
    approver?: string;
  }) =>
    apiFetch<Record<string, unknown>>("/islm/lifecycle/approve", {
      method: "POST",
      body,
    }),
};

/** Institutional Experimentation Platform — research governance (read-only) */
export const iepApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/iep/dashboard"),
  registry: (limit = 100) =>
    apiFetch<Record<string, unknown>>(`/iep/registry?limit=${limit}`),
  experiment: (experimentId: string) =>
    apiFetch<Record<string, unknown>>(
      `/iep/experiments/${encodeURIComponent(experimentId)}`,
    ),
  hypothesis: () => apiFetch<Record<string, unknown>>("/iep/hypothesis"),
  comparison: () => apiFetch<Record<string, unknown>>("/iep/comparison"),
  evidence: (experimentId?: string) =>
    apiFetch<Record<string, unknown>>(
      experimentId
        ? `/iep/evidence?experiment_id=${encodeURIComponent(experimentId)}`
        : "/iep/evidence",
    ),
  decisions: () => apiFetch<Record<string, unknown>>("/iep/decisions"),
  statistics: (experimentId?: string) =>
    apiFetch<Record<string, unknown>>(
      experimentId
        ? `/iep/statistics?experiment_id=${encodeURIComponent(experimentId)}`
        : "/iep/statistics",
    ),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/iep/reports?limit=${limit}`),
};

/** Institutional Control Plane — executive operations (read-only) */
export const icpApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/icp/dashboard"),
  health: () => apiFetch<Record<string, unknown>>("/icp/health"),
  alerts: () => apiFetch<Record<string, unknown>>("/icp/alerts"),
  timeline: () => apiFetch<Record<string, unknown>>("/icp/timeline"),
  dependencies: () => apiFetch<Record<string, unknown>>("/icp/dependencies"),
  evidence: () => apiFetch<Record<string, unknown>>("/icp/evidence"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/icp/reports?limit=${limit}`),
};

/** QuantForg Certification Suite — institutional quality gate (read-only) */
export const qcsApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qcs/dashboard"),
  readiness: () => apiFetch<Record<string, unknown>>("/qcs/readiness"),
  scores: () => apiFetch<Record<string, unknown>>("/qcs/scores"),
  checks: () => apiFetch<Record<string, unknown>>("/qcs/checks"),
  blockers: () => apiFetch<Record<string, unknown>>("/qcs/blockers"),
  evidence: () => apiFetch<Record<string, unknown>>("/qcs/evidence"),
  timeline: () => apiFetch<Record<string, unknown>>("/qcs/timeline"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/qcs/reports?limit=${limit}`),
};

/** QuantForg Strategy Marketplace & Registry — read-only strategy catalog */
export const qsmrApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qsmr/dashboard"),
  registry: (limit = 100) =>
    apiFetch<Record<string, unknown>>(`/qsmr/registry?limit=${limit}`),
  strategy: (strategyId: string) =>
    apiFetch<Record<string, unknown>>(
      `/qsmr/strategies/${encodeURIComponent(strategyId)}`,
    ),
  search: (params?: {
    q?: string;
    status?: string;
    lifecycle?: string;
    owner?: string;
    certification_status?: string;
    sort_by?: string;
    sort_dir?: string;
    group_by?: string;
    limit?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.q) sp.set("q", params.q);
    if (params?.status) sp.set("status", params.status);
    if (params?.lifecycle) sp.set("lifecycle", params.lifecycle);
    if (params?.owner) sp.set("owner", params.owner);
    if (params?.certification_status)
      sp.set("certification_status", params.certification_status);
    if (params?.sort_by) sp.set("sort_by", params.sort_by);
    if (params?.sort_dir) sp.set("sort_dir", params.sort_dir);
    if (params?.group_by) sp.set("group_by", params.group_by);
    if (params?.limit != null) sp.set("limit", String(params.limit));
    const qs = sp.toString();
    return apiFetch<Record<string, unknown>>(
      qs ? `/qsmr/search?${qs}` : "/qsmr/search",
    );
  },
  compare: (ids?: string[]) =>
    apiFetch<Record<string, unknown>>(
      ids?.length
        ? `/qsmr/compare?ids=${encodeURIComponent(ids.join(","))}`
        : "/qsmr/compare",
    ),
  evidence: (strategyId?: string) =>
    apiFetch<Record<string, unknown>>(
      strategyId
        ? `/qsmr/evidence?strategy_id=${encodeURIComponent(strategyId)}`
        : "/qsmr/evidence",
    ),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/qsmr/reports?limit=${limit}`),
};

/** QuantForg Portfolio Manager — read-only portfolio orchestration */
export const qpmApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qpm/dashboard"),
  allocation: () => apiFetch<Record<string, unknown>>("/qpm/allocation"),
  ranking: () => apiFetch<Record<string, unknown>>("/qpm/ranking"),
  diversification: () =>
    apiFetch<Record<string, unknown>>("/qpm/diversification"),
  metrics: () => apiFetch<Record<string, unknown>>("/qpm/metrics"),
  recommendations: () =>
    apiFetch<Record<string, unknown>>("/qpm/recommendations"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/qpm/reports?limit=${limit}`),
};

/** QuantForg Autonomous Operations Center — read-only operational orchestration */
export const aocApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/aoc/dashboard"),
  recommendations: () =>
    apiFetch<Record<string, unknown>>("/aoc/recommendations"),
  queue: () => apiFetch<Record<string, unknown>>("/aoc/queue"),
  scores: () => apiFetch<Record<string, unknown>>("/aoc/scores"),
  evidence: () => apiFetch<Record<string, unknown>>("/aoc/evidence"),
  brief: () => apiFetch<Record<string, unknown>>("/aoc/brief"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/aoc/reports?limit=${limit}`),
};

/** QuantForg Event Mesh — read-only immutable event distribution */
export const qemApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qem/dashboard"),
  events: (limit = 100) =>
    apiFetch<Record<string, unknown>>(`/qem/events?limit=${limit}`),
  stream: (limit = 100) =>
    apiFetch<Record<string, unknown>>(`/qem/stream?limit=${limit}`),
  timeline: (limit = 100) =>
    apiFetch<Record<string, unknown>>(`/qem/timeline?limit=${limit}`),
  search: (params?: {
    strategy_id?: string;
    release_id?: string;
    experiment_id?: string;
    correlation_id?: string;
    category?: string;
    event_type?: string;
    q?: string;
    limit?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params?.strategy_id) sp.set("strategy_id", params.strategy_id);
    if (params?.release_id) sp.set("release_id", params.release_id);
    if (params?.experiment_id) sp.set("experiment_id", params.experiment_id);
    if (params?.correlation_id) sp.set("correlation_id", params.correlation_id);
    if (params?.category) sp.set("category", params.category);
    if (params?.event_type) sp.set("event_type", params.event_type);
    if (params?.q) sp.set("q", params.q);
    sp.set("limit", String(params?.limit ?? 100));
    return apiFetch<Record<string, unknown>>(`/qem/search?${sp}`);
  },
  replay: (params?: { from_ts?: string; to_ts?: string; limit?: number }) => {
    const sp = new URLSearchParams();
    if (params?.from_ts) sp.set("from_ts", params.from_ts);
    if (params?.to_ts) sp.set("to_ts", params.to_ts);
    sp.set("limit", String(params?.limit ?? 200));
    return apiFetch<Record<string, unknown>>(`/qem/replay?${sp}`);
  },
  correlation: (correlationId?: string) =>
    correlationId
      ? apiFetch<Record<string, unknown>>(
          `/qem/correlation/${encodeURIComponent(correlationId)}`,
        )
      : apiFetch<Record<string, unknown>>("/qem/correlation"),
  subscribers: () => apiFetch<Record<string, unknown>>("/qem/subscribers"),
};

/** QuantForg Canonical Data Model — read-only enterprise schema contract */
export const qcdmApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qcdm/dashboard"),
  models: () => apiFetch<Record<string, unknown>>("/qcdm/models"),
  model: (model: string) =>
    apiFetch<Record<string, unknown>>(
      `/qcdm/models/${encodeURIComponent(model)}`,
    ),
  relationships: () =>
    apiFetch<Record<string, unknown>>("/qcdm/relationships"),
  governance: () => apiFetch<Record<string, unknown>>("/qcdm/governance"),
  timeline: () => apiFetch<Record<string, unknown>>("/qcdm/timeline"),
  validate: () => apiFetch<Record<string, unknown>>("/qcdm/validate"),
  schema: (model?: string) => {
    const sp = new URLSearchParams();
    if (model) sp.set("model", model);
    const q = sp.toString();
    return apiFetch<Record<string, unknown>>(
      q ? `/qcdm/schema?${q}` : "/qcdm/schema",
    );
  },
};

/** QuantForg Decision Intelligence Engine — advisory recommendations only */
export const qdieApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qdie/dashboard"),
  recommendations: () =>
    apiFetch<Record<string, unknown>>("/qdie/recommendations"),
  scores: () => apiFetch<Record<string, unknown>>("/qdie/scores"),
  evidence: () => apiFetch<Record<string, unknown>>("/qdie/evidence"),
  tradeoffs: () => apiFetch<Record<string, unknown>>("/qdie/tradeoffs"),
  brief: () => apiFetch<Record<string, unknown>>("/qdie/brief"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/qdie/reports?limit=${limit}`),
  history: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/qdie/history?limit=${limit}`),
};

/** QuantForg Strategy Factory — governed idea→paper pipeline (human-gated) */
export const qsfApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qsf/dashboard"),
  pipeline: () => apiFetch<Record<string, unknown>>("/qsf/pipeline"),
  workItems: () => apiFetch<Record<string, unknown>>("/qsf/work-items"),
  dossiers: () => apiFetch<Record<string, unknown>>("/qsf/dossiers"),
  evidence: () => apiFetch<Record<string, unknown>>("/qsf/evidence"),
  approvals: () => apiFetch<Record<string, unknown>>("/qsf/approvals"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/qsf/reports?limit=${limit}`),
  approve: (body: {
    strategy_id: string;
    to_stage: string;
    decision: "approved" | "rejected";
    comment?: string;
    approver?: string;
    work_item_id?: string;
  }) =>
    apiFetch<Record<string, unknown>>("/qsf/pipeline/approve", {
      method: "POST",
      body,
    }),
};

/** QuantForg Paper Trading Campaign Manager — paper-only, human-gated */
export const qptcmApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qptcm/dashboard"),
  campaigns: () => apiFetch<Record<string, unknown>>("/qptcm/campaigns"),
  timeline: () => apiFetch<Record<string, unknown>>("/qptcm/timeline"),
  evidence: () => apiFetch<Record<string, unknown>>("/qptcm/evidence"),
  graduation: () => apiFetch<Record<string, unknown>>("/qptcm/graduation"),
  reports: (limit = 20) =>
    apiFetch<Record<string, unknown>>(`/qptcm/reports?limit=${limit}`),
  approvals: () => apiFetch<Record<string, unknown>>("/qptcm/approvals"),
  approve: (body: {
    campaign_id: string;
    to_state: string;
    decision: "approved" | "rejected";
    comment?: string;
    approver?: string;
  }) =>
    apiFetch<Record<string, unknown>>("/qptcm/lifecycle/approve", {
      method: "POST",
      body,
    }),
};

/** Quant Knowledge Graph — read-only institutional knowledge layer */
export const qkgApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/qkg/dashboard"),
  graph: (limitNodes = 200, limitEdges = 400) =>
    apiFetch<Record<string, unknown>>(
      `/qkg/graph?limit_nodes=${limitNodes}&limit_edges=${limitEdges}`,
    ),
  search: (q?: string, nodeType?: string, limit = 50) => {
    const sp = new URLSearchParams();
    sp.set("limit", String(limit));
    if (q) sp.set("q", q);
    if (nodeType) sp.set("node_type", nodeType);
    return apiFetch<Record<string, unknown>>(`/qkg/search?${sp}`);
  },
  relationships: (nodeId: string) =>
    apiFetch<Record<string, unknown>>(
      `/qkg/relationships/${encodeURIComponent(nodeId)}`,
    ),
  dependencies: (nodeId: string, depth = 3) =>
    apiFetch<Record<string, unknown>>(
      `/qkg/dependencies/${encodeURIComponent(nodeId)}?depth=${depth}`,
    ),
  evidence: (nodeId: string) =>
    apiFetch<Record<string, unknown>>(
      `/qkg/evidence/${encodeURIComponent(nodeId)}`,
    ),
  recommendationTrace: (id: string) =>
    apiFetch<Record<string, unknown>>(
      `/qkg/recommendation-trace/${encodeURIComponent(id)}`,
    ),
  lineage: (nodeId: string) =>
    apiFetch<Record<string, unknown>>(
      `/qkg/lineage/${encodeURIComponent(nodeId)}`,
    ),
  impact: (nodeId: string) =>
    apiFetch<Record<string, unknown>>(
      `/qkg/impact/${encodeURIComponent(nodeId)}`,
    ),
  rootCause: (nodeId: string) =>
    apiFetch<Record<string, unknown>>(
      `/qkg/root-cause/${encodeURIComponent(nodeId)}`,
    ),
  ai: (q: string, nodeId?: string) => {
    const sp = new URLSearchParams();
    sp.set("q", q);
    if (nodeId) sp.set("node_id", nodeId);
    return apiFetch<Record<string, unknown>>(`/qkg/ai?${sp}`);
  },
};

/** Institutional Research Lab — completely isolated from production trading */
export const irlApi = {
  dashboard: () => apiFetch<Record<string, unknown>>("/irl/dashboard"),
  experiments: (limit = 100) =>
    apiFetch<Record<string, unknown>>(`/irl/experiments?limit=${limit}`),
  createExperiment: (body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>("/irl/experiments", {
      method: "POST",
      body,
    }),
  experiment: (id: string) =>
    apiFetch<Record<string, unknown>>(`/irl/experiments/${encodeURIComponent(id)}`),
  updateExperiment: (id: string, body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(`/irl/experiments/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body,
    }),
  replay: (id: string, body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      `/irl/experiments/${encodeURIComponent(id)}/replay`,
      { method: "POST", body },
    ),
  jobs: (limit = 50, experimentId?: string) => {
    const q = experimentId
      ? `?limit=${limit}&experiment_id=${encodeURIComponent(experimentId)}`
      : `?limit=${limit}`;
    return apiFetch<Record<string, unknown>>(`/irl/jobs${q}`);
  },
  leaderboard: (rankBy = "composite", limit = 50) =>
    apiFetch<Record<string, unknown>>(
      `/irl/leaderboard?rank_by=${encodeURIComponent(rankBy)}&limit=${limit}`,
    ),
  reports: (limit = 50) =>
    apiFetch<Record<string, unknown>>(`/irl/reports?limit=${limit}`),
  benchmark: () => apiFetch<Record<string, unknown>>("/irl/benchmark"),
  addNote: (id: string, body: Record<string, unknown>) =>
    apiFetch<Record<string, unknown>>(
      `/irl/experiments/${encodeURIComponent(id)}/notes`,
      { method: "POST", body },
    ),
  archive: (id: string) =>
    apiFetch<Record<string, unknown>>(
      `/irl/experiments/${encodeURIComponent(id)}/archive`,
      { method: "POST", body: {} },
    ),
  setVerdict: (id: string, verdict: string) =>
    apiFetch<Record<string, unknown>>(
      `/irl/experiments/${encodeURIComponent(id)}/verdict`,
      { method: "POST", body: { verdict } },
    ),
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
