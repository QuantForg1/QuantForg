"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { mt5Api, platformApi, portfolioApi, weltradeApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useBrokerStatusStream, useBookStream } from "@/hooks/realtime";
import {
  gatewayDiagnosticDetail,
  gatewayStatusLabel,
} from "@/lib/gateway-diagnostics";
import { useAuth } from "@/providers/auth-provider";
import { ApiError } from "@/lib/api/client";
import {
  mergePlaneOk,
  planeConnectionLabel,
  resolveTradingComponentsView,
} from "@/lib/trading/component-health";

export type TradingSessionState = {
  connected: boolean;
  /** null = unknown (do not invent disconnected from API/auth outage). */
  gatewayOnline: boolean | null;
  /** null = unknown. */
  brokerConnected: boolean | null;
  /**
   * Explicit EXECUTION_ENABLED from gateway health when present.
   * null = unknown — callers must not invent Enabled.
   */
  executionEnabled: boolean | null;
  /** True once weltrade health has settled (success or error). */
  healthKnown: boolean;
  login: string;
  server: string;
  balance: string;
  equity: string;
  freeMargin: string;
  margin: string;
  marginLevel: string;
  profit: string;
  leverage: string;
  currency: string;
  loginStatus: string;
  latencyMs: string;
  heartbeatAt: string;
  gatewayLabel: string;
  gatewayDetail: string;
  gatewayUrl: string;
  positions: Record<string, unknown>[];
  orders: Record<string, unknown>[];
  historyDeals: Record<string, unknown>[];
  refreshing: boolean;
  invalidateAll: () => Promise<void>;
};

const TradingSessionContext = createContext<TradingSessionState | null>(null);

/** Shared broker session for the whole app shell — one source of truth. */
export function TradingSessionProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const { isAuthenticated, loading: authLoading, opsReady } = useAuth();
  // Wait for auth bootstrap — never race protected probes ahead of /auth/me.
  const sessionEnabled = opsReady && isAuthenticated && !authLoading;

  const componentsQ = useQuery({
    queryKey: ["trading-components-health"],
    queryFn: platformApi.tradingComponents,
    staleTime: 15_000,
    retry: 1,
  });
  const componentsError =
    componentsQ.error instanceof ApiError ? componentsQ.error : null;
  const componentsView = resolveTradingComponentsView({
    payload: componentsQ.data,
    isSuccess: componentsQ.isSuccess,
    isError: componentsQ.isError,
    errorKind:
      componentsError?.code === "timeout"
        ? "timeout"
        : componentsError?.code === "network_error"
          ? "network"
          : componentsQ.isError
            ? "other"
            : null,
  });

  useBrokerStatusStream(sessionEnabled);

  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    staleTime: 15_000,
    retry: 1,
    enabled: sessionEnabled,
  });

  const statusQ = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    staleTime: 5_000,
    retry: 1,
    // Run after health settles so cold Railway workers heal/bind first.
    enabled: sessionEnabled && (healthQ.isFetched || healthQ.isError),
  });
  const statusConnected = Boolean(asRecord(statusQ.data).connected);
  const healthPreview = asRecord(healthQ.data);
  const healthUsablePreview =
    healthQ.isSuccess && Object.keys(healthPreview).length > 0;
  const healthAttached = Boolean(
    healthPreview.weltrade_connected ||
      healthPreview.mt5_connected ||
      healthPreview.mt5_attached,
  );
  // Prefer MT5 status; fall back to weltrade health while status heals.
  const connectedFlag =
    statusConnected || (healthUsablePreview && healthAttached);

  // Keep the MT5 book hot whenever the session is attached (all app surfaces).
  useBookStream(connectedFlag);

  const portfolioQ = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    staleTime: 5_000,
    retry: 1,
    enabled: connectedFlag,
  });
  const positionsQ = useQuery({
    queryKey: ["positions"],
    queryFn: () => portfolioApi.positions(),
    staleTime: 4_000,
    retry: 1,
    enabled: connectedFlag,
  });
  const ordersQ = useQuery({
    queryKey: ["orders"],
    queryFn: portfolioApi.orders,
    staleTime: 4_000,
    retry: 1,
    enabled: connectedFlag,
  });
  const historyQ = useQuery({
    queryKey: ["history"],
    queryFn: portfolioApi.history,
    staleTime: 8_000,
    retry: 1,
    enabled: connectedFlag,
  });

  const status = asRecord(statusQ.data);
  const portfolio = asRecord(portfolioQ.data);
  const account = asRecord(portfolio.account);
  const health = healthPreview;

  const connected = connectedFlag || componentsView?.mt5.ok === true;
  // Health feed may 500 under DB pressure — do not treat that as broker down
  // when MT5 status already proves an attached session.
  const healthKnown =
    (healthQ.isFetched && !healthQ.isLoading) ||
    (statusQ.isFetched && !statusQ.isLoading) ||
    Boolean(componentsView);
  const healthUsable = healthUsablePreview;
  // Authoritative trading-components first. Session/weltrade are secondary
  // and must not collapse API/auth outages into Disconnected.
  const gatewayOnline = mergePlaneOk(
    componentsView?.gateway.ok ?? null,
    healthUsable ? Boolean(health.gateway_online || health.gateway_reachable) : null,
  );
  const brokerConnected = mergePlaneOk(
    componentsView?.mt5.ok ?? null,
    healthUsable
      ? Boolean(health.weltrade_connected || health.mt5_connected || connectedFlag)
      : connectedFlag
        ? true
        : null,
  );
  const executionEnabled =
    healthUsable && "execution_enabled" in health
      ? Boolean(health.execution_enabled)
      : null;

  const gatewayDetail = healthUsable
    ? gatewayDiagnosticDetail(health)
    : componentsView?.gateway.ok === true
      ? str(componentsView.gateway.detail, "Authoritative trading-components")
      : healthQ.isError
        ? "Broker health feed unavailable — using trading-components"
        : "";
  const gatewayLabel =
    gatewayOnline === true
      ? componentsView?.gateway.stale
        ? "Gateway Online (cached)"
        : "Gateway Online"
      : healthUsable
        ? gatewayStatusLabel(health)
        : planeConnectionLabel(gatewayOnline, Boolean(componentsView?.gateway.stale));

  // After health reports an attached gateway session, refresh MT5 status so
  // ticks/symbols see the healed process-local handle.
  const healedOnce = useRef(false);
  useEffect(() => {
    if (!sessionEnabled || !healthUsable || !healthAttached) return;
    if (statusConnected) {
      healedOnce.current = false;
      return;
    }
    if (healedOnce.current) return;
    healedOnce.current = true;
    void qc.invalidateQueries({ queryKey: ["mt5-status"] });
  }, [sessionEnabled, healthUsable, healthAttached, statusConnected, qc]);

  const invalidateAll = useCallback(async () => {
    // Drop all broker/gateway caches so reconnect never serves stale status.
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["mt5-status"] }),
      qc.invalidateQueries({ queryKey: ["portfolio"] }),
      qc.invalidateQueries({ queryKey: ["orders"] }),
      qc.invalidateQueries({ queryKey: ["positions"] }),
      qc.invalidateQueries({ queryKey: ["history"] }),
      qc.invalidateQueries({ queryKey: ["mt5-symbols"] }),
      qc.invalidateQueries({ queryKey: ["mt5-tick"] }),
      qc.invalidateQueries({ queryKey: ["weltrade-health"] }),
      qc.invalidateQueries({ queryKey: ["weltrade-dashboard"] }),
      qc.invalidateQueries({ queryKey: ["brokers"] }),
      qc.invalidateQueries({ queryKey: ["mt5-account"] }),
      qc.invalidateQueries({ queryKey: ["portfolio-positions"] }),
    ]);
  }, [qc]);

  const prevConnected = useRef<boolean | null>(null);
  useEffect(() => {
    // On reconnect (false → true) or disconnect, flush stale gateway caches.
    if (prevConnected.current === null) {
      prevConnected.current = connected;
      return;
    }
    if (prevConnected.current !== connected) {
      prevConnected.current = connected;
      void invalidateAll();
    }
  }, [connected, invalidateAll]);

  const positions = useMemo(() => {
    // Dedicated /positions is source of truth so closes leave Open Positions immediately.
    if (positionsQ.isFetched) return asList(positionsQ.data).map(asRecord);
    return asList(portfolio.positions).map(asRecord);
  }, [positionsQ.isFetched, positionsQ.data, portfolio.positions]);

  const orders = useMemo(() => {
    if (ordersQ.isFetched) return asList(ordersQ.data).map(asRecord);
    return asList(portfolio.pending_orders).map(asRecord);
  }, [ordersQ.isFetched, ordersQ.data, portfolio.pending_orders]);

  const historyDeals = useMemo(() => {
    const hist = asRecord(historyQ.data);
    const deals = asList(hist.deals ?? historyQ.data).map(asRecord);
    return deals;
  }, [historyQ.data]);

  const value = useMemo<TradingSessionState>(
    () => ({
      connected,
      gatewayOnline,
      brokerConnected,
      executionEnabled,
      healthKnown,
      login: str(account.login || status.login, "—"),
      server: str(account.server || status.server, "—"),
      balance: str(account.balance, "—"),
      equity: str(account.equity, "—"),
      freeMargin: str(account.free_margin, "—"),
      margin: str(account.margin, "—"),
      marginLevel: str(account.margin_level, "—"),
      profit: str(account.profit, "—"),
      leverage: str(account.leverage, "—"),
      currency: str(account.currency, ""),
      loginStatus: str(status.login_status || health.login_status, "logged_out"),
      latencyMs: str(status.latency_ms ?? health.latency_ms ?? health.latency, "—"),
      heartbeatAt: str(status.last_heartbeat_at || health.last_heartbeat_at, ""),
      gatewayLabel,
      gatewayDetail,
      gatewayUrl: str(health.gateway_url, ""),
      positions,
      orders,
      historyDeals,
      refreshing:
        statusQ.isFetching ||
        portfolioQ.isFetching ||
        healthQ.isFetching ||
        positionsQ.isFetching ||
        ordersQ.isFetching ||
        historyQ.isFetching,
      invalidateAll,
    }),
    [
      connected,
      gatewayOnline,
      brokerConnected,
      executionEnabled,
      healthKnown,
      account,
      status,
      health,
      gatewayLabel,
      gatewayDetail,
      positions,
      orders,
      historyDeals,
      statusQ.isFetching,
      portfolioQ.isFetching,
      healthQ.isFetching,
      positionsQ.isFetching,
      ordersQ.isFetching,
      historyQ.isFetching,
      invalidateAll,
    ],
  );

  return (
    <TradingSessionContext.Provider value={value}>
      {children}
    </TradingSessionContext.Provider>
  );
}

export function useTradingSession(): TradingSessionState {
  const ctx = useContext(TradingSessionContext);
  if (!ctx) {
    throw new Error("useTradingSession requires TradingSessionProvider");
  }
  return ctx;
}

/** Safe for pages that may render outside the shell. */
export function useTradingSessionOptional(): TradingSessionState | null {
  return useContext(TradingSessionContext);
}
