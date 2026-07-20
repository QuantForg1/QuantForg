"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { mt5Api, portfolioApi, weltradeApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useBrokerStatusStream, useBookStream } from "@/hooks/realtime";
import {
  gatewayDiagnosticDetail,
  gatewayStatusLabel,
} from "@/lib/gateway-diagnostics";

export type TradingSessionState = {
  connected: boolean;
  gatewayOnline: boolean;
  brokerConnected: boolean;
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
  useBrokerStatusStream(true);

  const statusQ = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    staleTime: 5_000,
    retry: 1,
  });
  const connectedFlag = Boolean(asRecord(statusQ.data).connected);

  // Keep the MT5 book hot whenever the session is attached (all app surfaces).
  useBookStream(connectedFlag);

  const portfolioQ = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    staleTime: 5_000,
    retry: 1,
    enabled: connectedFlag,
  });
  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    staleTime: 15_000,
    retry: 1,
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
  const health = asRecord(healthQ.data);

  const connected = Boolean(status.connected);
  const gatewayOnline = Boolean(
    health.gateway_online || health.gateway_reachable || connected,
  );
  const brokerConnected = Boolean(
    health.weltrade_connected || health.mt5_connected || connected,
  );

  const gatewayDetail = gatewayDiagnosticDetail(health);
  const gatewayLabel = gatewayOnline
    ? "Gateway Online"
    : gatewayStatusLabel(health);

  const invalidateAll = useCallback(async () => {
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
    ]);
  }, [qc]);

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
