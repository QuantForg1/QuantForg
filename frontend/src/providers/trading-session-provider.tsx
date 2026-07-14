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
import { asRecord, str } from "@/lib/desk";
import { useBrokerStatusStream } from "@/hooks/realtime";

export type TradingSessionState = {
  connected: boolean;
  gatewayOnline: boolean;
  login: string;
  server: string;
  balance: string;
  equity: string;
  freeMargin: string;
  margin: string;
  leverage: string;
  currency: string;
  loginStatus: string;
  latencyMs: string;
  heartbeatAt: string;
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
    refetchInterval: 10_000,
    retry: 1,
  });
  const portfolioQ = useQuery({
    queryKey: ["portfolio"],
    queryFn: portfolioApi.get,
    refetchInterval: 12_000,
    retry: 1,
    enabled: Boolean(asRecord(statusQ.data).connected),
  });
  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    refetchInterval: 15_000,
    retry: 1,
  });

  const status = asRecord(statusQ.data);
  const portfolio = asRecord(portfolioQ.data);
  const account = asRecord(portfolio.account);
  const health = asRecord(healthQ.data);

  const connected = Boolean(status.connected);
  const gatewayOnline = Boolean(
    health.gateway_online || health.gateway_reachable || connected,
  );

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
    ]);
  }, [qc]);

  const value = useMemo<TradingSessionState>(
    () => ({
      connected,
      gatewayOnline,
      login: str(account.login || status.login, "—"),
      server: str(account.server || status.server, "—"),
      balance: str(account.balance, "—"),
      equity: str(account.equity, "—"),
      freeMargin: str(account.free_margin, "—"),
      margin: str(account.margin, "—"),
      leverage: str(account.leverage, "—"),
      currency: str(account.currency, ""),
      loginStatus: str(status.login_status || health.login_status, "logged_out"),
      latencyMs: str(status.latency_ms ?? health.latency_ms ?? health.latency, "—"),
      heartbeatAt: str(status.last_heartbeat_at || health.detail, ""),
      refreshing:
        statusQ.isFetching || portfolioQ.isFetching || healthQ.isFetching,
      invalidateAll,
    }),
    [
      connected,
      gatewayOnline,
      account,
      status,
      health,
      statusQ.isFetching,
      portfolioQ.isFetching,
      healthQ.isFetching,
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
