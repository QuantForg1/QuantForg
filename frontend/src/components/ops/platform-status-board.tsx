"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import {
  getApiConnectionState,
  subscribeApiConnection,
  type ApiConnectionState,
} from "@/lib/api/connectivity";
import {
  iteOpsApi,
  mt5Api,
  platformApi,
  signalCenterApi,
  weltradeApi,
} from "@/lib/api/endpoints";
import { asRecord, num, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";
import { useEffect, useState } from "react";

type Tone = "success" | "warning" | "danger" | "neutral";

type CardModel = {
  id: string;
  title: string;
  status: string;
  tone: Tone;
  latency?: string;
  heartbeat?: string;
  detail?: string;
  metrics?: Array<{ label: string; value: string }>;
};

function toneFromOk(ok: boolean | null, warn = false): Tone {
  if (ok == null) return "neutral";
  if (ok) return "success";
  return warn ? "warning" : "danger";
}

function StatusCard({ card }: { card: CardModel }) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)] px-3 py-3">
      <header className="flex items-start justify-between gap-2">
        <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          {card.title}
        </h3>
        <Badge tone={card.tone} className="h-5 shrink-0 px-1.5 text-[10px]">
          {card.status}
        </Badge>
      </header>
      {card.detail ? (
        <p className="mt-2 text-[12px] text-[var(--fg-muted)]">{card.detail}</p>
      ) : null}
      <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
        {card.latency ? (
          <>
            <dt className="text-[var(--fg-subtle)]">Latency</dt>
            <dd className="tabular text-[var(--fg)]">{card.latency}</dd>
          </>
        ) : null}
        {card.heartbeat ? (
          <>
            <dt className="text-[var(--fg-subtle)]">Heartbeat</dt>
            <dd className="tabular text-[var(--fg)]">{card.heartbeat}</dd>
          </>
        ) : null}
        {(card.metrics ?? []).map((m) => (
          <div key={m.label} className="contents">
            <dt className="text-[var(--fg-subtle)]">{m.label}</dt>
            <dd className="tabular text-[var(--fg)]">{m.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/**
 * Independent production status board.
 * Backend / Gateway / MT5 / Broker / Session never collapse into one Offline bit.
 */
export function PlatformStatusBoard() {
  const { isAuthenticated, user } = useAuth();
  const session = useTradingSession();
  const [apiState, setApiState] = useState<ApiConnectionState>(() =>
    getApiConnectionState(),
  );

  useEffect(() => subscribeApiConnection(setApiState), []);

  const backendQ = useQuery({
    queryKey: ["platform-health", "mission"],
    queryFn: platformApi.health,
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: 1,
  });
  const weltradeQ = useQuery({
    queryKey: ["weltrade-health", "mission"],
    queryFn: weltradeApi.health,
    staleTime: 15_000,
    refetchInterval: 30_000,
    retry: 1,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status", "mission"],
    queryFn: mt5Api.status,
    staleTime: 10_000,
    refetchInterval: 20_000,
    retry: 1,
  });
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "mission"],
    queryFn: iteOpsApi.autoTrading,
    staleTime: 20_000,
    refetchInterval: 30_000,
    retry: false,
  });
  const signalsQ = useQuery({
    queryKey: ["signals-center", "mission"],
    queryFn: () => signalCenterApi.list({}),
    staleTime: 20_000,
    refetchInterval: 45_000,
    retry: false,
  });

  const health = asRecord(weltradeQ.data);
  const mt5 = asRecord(mt5Q.data);
  const auto = asRecord(autoQ.data);
  const live = asRecord(auto.live);
  const dash = asRecord(signalsQ.data?.dashboard);
  const positions = session.positions;

  const cards = useMemo((): CardModel[] => {
    const backendOk =
      backendQ.isSuccess || apiState === "reachable"
        ? true
        : backendQ.isError || apiState === "unreachable"
          ? false
          : apiState === "degraded"
            ? null
            : null;
    const gatewayOk = session.healthKnown
      ? session.gatewayOnline
      : health.gateway_online != null
        ? Boolean(health.gateway_online || health.gateway_reachable)
        : null;
    const mt5Ok =
      mt5.connected != null
        ? Boolean(mt5.connected)
        : session.connected
          ? true
          : mt5Q.isFetched
            ? false
            : null;
    const brokerOk = session.healthKnown
      ? session.brokerConnected
      : health.weltrade_connected != null
        ? Boolean(health.weltrade_connected || health.mt5_connected)
        : mt5Ok;

    const openN = positions.length;
    const floatPnl = positions.reduce((s, p) => s + num(p.profit, 0), 0);

    return [
      {
        id: "backend",
        title: "Backend",
        status:
          backendOk === true
            ? "Online"
            : backendOk === false
              ? "Unreachable"
              : apiState === "degraded"
                ? "Degraded"
                : "Checking",
        tone: toneFromOk(backendOk, apiState === "degraded"),
        latency: backendQ.dataUpdatedAt
          ? `${Math.max(0, Date.now() - backendQ.dataUpdatedAt)} ms ago`
          : "—",
        heartbeat: backendQ.isSuccess ? "OK" : backendQ.isError ? "Error" : "—",
        detail:
          apiState === "degraded"
            ? "Elevated latency — not the same as offline"
            : undefined,
      },
      {
        id: "gateway",
        title: "Gateway",
        status:
          gatewayOk === true
            ? "Connected"
            : gatewayOk === false
              ? "Disconnected"
              : "Unknown",
        tone: toneFromOk(gatewayOk),
        latency: str(session.latencyMs, "—"),
        heartbeat: str(session.heartbeatAt, "—").slice(0, 19) || "—",
        detail: session.gatewayLabel || undefined,
      },
      {
        id: "mt5",
        title: "MT5",
        status: mt5Ok === true ? "Running" : mt5Ok === false ? "Detached" : "Unknown",
        tone: toneFromOk(mt5Ok),
        metrics: [
          { label: "Login", value: str(session.login, "—") },
          { label: "Server", value: str(session.server, "—") },
        ],
      },
      {
        id: "broker",
        title: "Broker",
        status:
          brokerOk === true
            ? "Connected"
            : brokerOk === false
              ? "Disconnected"
              : "Unknown",
        tone: toneFromOk(brokerOk),
        metrics: [
          { label: "Equity", value: str(session.equity, "—") },
          { label: "Open", value: String(openN) },
        ],
      },
      {
        id: "session",
        title: "Session",
        status: isAuthenticated ? "Authenticated" : "Signed out",
        tone: isAuthenticated ? "success" : "warning",
        detail: user?.email || user?.display_name || undefined,
      },
      {
        id: "scanner",
        title: "Scanner",
        status: autoQ.isSuccess ? "Ready" : autoQ.isError ? "Error" : "—",
        tone: autoQ.isError ? "warning" : autoQ.isSuccess ? "success" : "neutral",
        metrics: [
          {
            label: "Eligible",
            value: str(
              asRecord(asRecord(auto.ai_scalping).scan).eligible_count,
              "—",
            ),
          },
        ],
      },
      {
        id: "ai",
        title: "AI",
        status: str(asRecord(auto.status), autoQ.isSuccess ? "Ready" : "—"),
        tone: "neutral",
        detail: str(asRecord(auto.primary_blocker), "") || undefined,
      },
      {
        id: "oms",
        title: "OMS",
        status: str(asRecord(auto.execution_state).ops_mode, "—"),
        tone: Boolean(asRecord(auto.execution_state).execution_enabled)
          ? "success"
          : "neutral",
        metrics: [
          { label: "Orders", value: String(session.orders.length) },
          { label: "Positions", value: String(openN) },
        ],
      },
      {
        id: "risk",
        title: "Risk",
        status: str(asRecord(auto.blocking_category), "Clear") || "Clear",
        tone: str(asRecord(auto.blocking_category)) ? "warning" : "success",
      },
      {
        id: "pme",
        title: "PME",
        status: str(live.pme_state || live.position_engine, "—"),
        tone: "neutral",
      },
      {
        id: "portfolio",
        title: "Portfolio",
        status: openN > 0 ? "Open book" : "Flat",
        tone: openN > 0 ? "success" : "neutral",
        metrics: [
          { label: "Float PnL", value: Number.isFinite(floatPnl) ? floatPnl.toFixed(2) : "—" },
          { label: "Positions", value: String(openN) },
        ],
      },
      {
        id: "signals",
        title: "Signals",
        status: signalsQ.isSuccess ? "LIVE" : signalsQ.isError ? "Error" : "—",
        tone: signalsQ.isSuccess ? "success" : signalsQ.isError ? "warning" : "neutral",
        metrics: [
          { label: "BUY", value: str(dash.buy_signals, "—") },
          { label: "SELL", value: str(dash.sell_signals, "—") },
          { label: "Enabled", value: str(dash.enabled_symbols, "—") },
        ],
      },
    ];
  }, [
    apiState,
    auto,
    autoQ.isError,
    autoQ.isSuccess,
    backendQ.dataUpdatedAt,
    backendQ.isError,
    backendQ.isSuccess,
    dash,
    health,
    isAuthenticated,
    live,
    mt5,
    mt5Q.isFetched,
    positions,
    session,
    signalsQ.isError,
    signalsQ.isSuccess,
    user,
  ]);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[12px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Production status
        </h2>
        <p className={cn("text-[11px] text-[var(--fg-subtle)]")}>
          Independent planes — a broker disconnect is not an API outage
        </p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {cards.map((card) => (
          <StatusCard key={card.id} card={card} />
        ))}
      </div>
    </div>
  );
}
