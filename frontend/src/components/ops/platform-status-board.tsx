"use client";

import { useEffect, useMemo, useState } from "react";
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
import { asRecord, num, statusLabel, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn } from "@/lib/utils";

type Tone = "success" | "warning" | "danger" | "neutral";

type CardModel = {
  id: string;
  title: string;
  status: string;
  tone: Tone;
  latency?: string;
  heartbeat?: string;
  version?: string;
  errors?: string;
  recovery?: string;
  detail?: string;
  metrics?: Array<{ label: string; value: string }>;
};

function toneFromOk(ok: boolean | null, warn = false): Tone {
  if (ok == null) return "neutral";
  if (ok) return "success";
  return warn ? "warning" : "danger";
}

function componentStatus(
  statuses: Record<string, unknown>,
  key: string,
): string {
  return str(statuses[key], "").toUpperCase();
}

async function timedHealthLive(): Promise<{
  payload: Record<string, unknown>;
  latencyMs: number;
}> {
  const started = performance.now();
  const payload = await platformApi.healthLive();
  return { payload, latencyMs: Math.round(performance.now() - started) };
}

async function timedTradingComponents(): Promise<{
  payload: Record<string, unknown>;
  latencyMs: number;
}> {
  const started = performance.now();
  const payload = await platformApi.tradingComponents();
  return { payload, latencyMs: Math.round(performance.now() - started) };
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
        {card.version ? (
          <>
            <dt className="text-[var(--fg-subtle)]">Version</dt>
            <dd className="tabular text-[var(--fg)]">{card.version}</dd>
          </>
        ) : null}
        {card.errors ? (
          <>
            <dt className="text-[var(--fg-subtle)]">Errors</dt>
            <dd className="tabular text-[var(--fg)]">{card.errors}</dd>
          </>
        ) : null}
        {card.recovery ? (
          <>
            <dt className="text-[var(--fg-subtle)]">Recovery</dt>
            <dd className="tabular text-[var(--fg)]">{card.recovery}</dd>
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

  // Shared query keys with TradingSessionProvider — React Query dedupes polls.
  const backendQ = useQuery({
    queryKey: ["platform-health-live"],
    queryFn: timedHealthLive,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  });
  const componentsQ = useQuery({
    queryKey: ["trading-components-health"],
    queryFn: timedTradingComponents,
    staleTime: 20_000,
    refetchInterval: 45_000,
    retry: 1,
  });
  const weltradeQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    staleTime: 20_000,
    refetchInterval: 45_000,
    retry: 1,
  });
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading"],
    queryFn: iteOpsApi.autoTrading,
    staleTime: 45_000,
    refetchInterval: 60_000,
    retry: false,
  });
  const signalsQ = useQuery({
    queryKey: ["signals-center", "mission"],
    queryFn: () => signalCenterApi.list({}),
    staleTime: 45_000,
    refetchInterval: 90_000,
    retry: false,
  });
  const versionQ = useQuery({
    queryKey: ["platform-version"],
    queryFn: platformApi.version,
    staleTime: 300_000,
    refetchInterval: 600_000,
    retry: false,
  });

  const health = asRecord(weltradeQ.data);
  const mt5 = asRecord(mt5Q.data);
  const auto = asRecord(autoQ.data);
  const live = asRecord(auto.live);
  const facts = asRecord(auto.facts);
  const execState = asRecord(auto.execution_state);
  const components = asRecord(componentsQ.data?.payload ?? componentsQ.data);
  const statuses = asRecord(components.statuses);
  const dash = asRecord(signalsQ.data?.dashboard);
  const positions = session.positions;
  const version = asRecord(versionQ.data);
  const versionLabel =
    str(version.version || version.git_sha || version.build || version.release, "—") ||
    "—";
  const backendLatencyMs = backendQ.data?.latencyMs ?? null;
  const componentsLatencyMs = componentsQ.data?.latencyMs ?? null;

  const cards = useMemo((): CardModel[] => {
    const backendOk =
      backendQ.isSuccess || apiState === "reachable"
        ? true
        : backendQ.isError || apiState === "unreachable"
          ? false
          : apiState === "degraded"
            ? null
            : null;

    const gwStatus = componentStatus(statuses, "gateway");
    const mt5Status = componentStatus(statuses, "mt5");
    const omsStatus = componentStatus(statuses, "oms");
    const aiStatus = componentStatus(statuses, "ai");

    const gatewayOk =
      gwStatus === "HEALTHY"
        ? true
        : gwStatus === "DOWN" || gwStatus === "UNHEALTHY"
          ? false
          : session.healthKnown
            ? session.gatewayOnline
            : health.gateway_online != null
              ? Boolean(health.gateway_online || health.gateway_reachable)
              : session.connected
                ? true
                : null;

    const mt5Ok =
      mt5Status === "CONNECTED"
        ? true
        : mt5Status === "DISCONNECTED" || mt5Status === "DOWN"
          ? false
          : mt5.connected != null
            ? Boolean(mt5.connected)
            : session.connected
              ? true
              : mt5Q.isFetched && !mt5Q.isError
                ? false
                : null;

    // Broker transport vs market session — do not conflate.
    const mt5Confirmed = mt5Ok === true;
    const brokerTransportOk = Boolean(
      mt5Confirmed ||
        facts.broker_connected ||
        (session.healthKnown && session.brokerConnected) ||
        health.weltrade_connected ||
        health.mt5_connected,
    );
    const marketSessionClosed =
      brokerTransportOk &&
      (str(health.login_status).toLowerCase().includes("close") ||
        str(session.loginStatus).toLowerCase() === "market_closed" ||
        Boolean(health.session_closed));
    const brokerHealthUnknown = Boolean(weltradeQ.isError && !mt5Confirmed);

    const openN = positions.length;
    const floatPnl = positions.reduce((s, p) => s + num(p.profit, 0), 0);

    const autoStatus = statusLabel(
      auto.status,
      autoQ.isSuccess ? "Ready" : autoQ.isError ? "Unavailable" : "—",
    );
    const blocker = statusLabel(auto.primary_blocker, "");
    const blockCat = statusLabel(auto.blocking_category, "");
    const riskClear = !blockCat || blockCat === "—" || blockCat.toLowerCase() === "none";
    const pmeLabel = statusLabel(
      live.pme_state || live.position_engine,
      openN === 0 ? "Synced (flat)" : "—",
    );
    const omsLabel =
      omsStatus ||
      statusLabel(execState.ops_mode, Boolean(execState.execution_enabled) ? "READY" : "—");

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
        latency:
          backendLatencyMs != null ? `${backendLatencyMs} ms` : "—",
        heartbeat: backendQ.isSuccess
          ? new Date(backendQ.dataUpdatedAt).toISOString().slice(11, 19)
          : backendQ.isError
            ? "Error"
            : "—",
        version: versionLabel,
        errors: backendQ.isError ? "Health probe failed" : "0",
        recovery:
          apiState === "degraded"
            ? "Soft retry"
            : apiState === "unreachable"
              ? "Probing"
              : "Stable",
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
            ? "HEALTHY"
            : gatewayOk === false
              ? "UNREACHABLE"
              : "UNKNOWN",
        tone: toneFromOk(gatewayOk),
        latency:
          componentsLatencyMs != null
            ? `${componentsLatencyMs} ms`
            : str(session.latencyMs, "—") !== "—"
              ? `${session.latencyMs} ms`
              : "—",
        heartbeat: str(session.heartbeatAt, "—").slice(0, 19) || "—",
        version: str(health.gateway_version || health.version, "—"),
        errors: gatewayOk === false ? statusLabel(health.diagnostic, "No heartbeat") : "0",
        recovery: gatewayOk === false ? "Await reconnect" : "Stable",
        detail: session.gatewayLabel || str(asRecord(components.gateway).detail, "") || undefined,
      },
      {
        id: "mt5",
        title: "MT5",
        status:
          mt5Ok === true
            ? "CONNECTED"
            : mt5Ok === false
              ? "DISCONNECTED"
              : "UNKNOWN",
        tone: toneFromOk(mt5Ok),
        heartbeat: str(mt5.updated_at || mt5.last_heartbeat, "—").slice(0, 19) || "—",
        version: str(mt5.build || mt5.terminal_build, "—"),
        errors: mt5Ok === false ? "Detached" : "0",
        recovery: mt5Ok === false ? "Await attach" : "Stable",
        metrics: [
          { label: "Login", value: str(session.login, "—") },
          { label: "Server", value: str(session.server, "—") },
        ],
      },
      {
        id: "broker",
        title: "Broker",
        status: !brokerTransportOk
          ? brokerHealthUnknown
            ? "UNKNOWN"
            : "DISCONNECTED"
          : marketSessionClosed
            ? "CONNECTED · SESSION CLOSED"
            : "CONNECTED",
        tone: !brokerTransportOk
          ? brokerHealthUnknown
            ? "neutral"
            : "danger"
          : marketSessionClosed
            ? "warning"
            : "success",
        heartbeat: str(health.as_of || health.updated_at, "—").slice(0, 19) || "—",
        version: str(health.broker || health.broker_name, "Weltrade"),
        errors: !brokerTransportOk
          ? brokerHealthUnknown
            ? "Health feed error"
            : "Session down"
          : "0",
        recovery: !brokerTransportOk
          ? "Reconnect available"
          : marketSessionClosed
            ? "Await session open"
            : "Stable",
        detail: !brokerTransportOk
          ? brokerHealthUnknown
            ? "Broker health request failed — using MT5/trading-components when available"
            : undefined
          : marketSessionClosed
            ? "Broker connected. No new market entries available during this session."
            : undefined,
        metrics: [
          { label: "Equity", value: str(session.equity, "—") },
          { label: "Open", value: String(openN) },
        ],
      },
      {
        id: "auth",
        title: "Authentication",
        status: isAuthenticated ? "Authenticated" : "Signed out",
        tone: isAuthenticated ? "success" : "warning",
        version: "—",
        errors: "0",
        recovery: isAuthenticated ? "Stable" : "Login required",
        detail: user?.email || user?.display_name || undefined,
      },
      {
        id: "database",
        title: "Database",
        status:
          backendOk === true
            ? "Reachable"
            : backendOk === false
              ? "Unknown"
              : "Checking",
        tone: toneFromOk(backendOk),
        version: versionLabel,
        errors: backendQ.isError ? "Via health" : "0",
        recovery: "Stable",
        detail: "Inferred from backend health — no fabricated DB metrics",
      },
      {
        id: "railway",
        title: "Railway",
        status:
          backendOk === true
            ? "Serving"
            : backendOk === false
              ? "Unreachable"
              : "Checking",
        tone: toneFromOk(backendOk, apiState === "degraded"),
        latency: backendLatencyMs != null ? `${backendLatencyMs} ms` : "—",
        version: versionLabel,
        errors: backendQ.isError ? "Deploy probe failed" : "0",
        recovery: apiState === "degraded" ? "Degraded path" : "Stable",
      },
      {
        id: "scanner",
        title: "Scanner",
        status:
          aiStatus === "HEALTHY" || autoQ.isSuccess
            ? "RUNNING"
            : autoQ.isError
              ? "UNKNOWN"
              : "—",
        tone:
          aiStatus === "HEALTHY" || autoQ.isSuccess
            ? "success"
            : autoQ.isError
              ? "warning"
              : "neutral",
        heartbeat: autoQ.dataUpdatedAt
          ? new Date(autoQ.dataUpdatedAt).toISOString().slice(11, 19)
          : "—",
        errors: autoQ.isError ? "Ops feed error" : "0",
        recovery: autoQ.isError ? "Retrying poll" : "Stable",
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
        id: "auto",
        title: "Auto Trading",
        status: autoStatus,
        tone: autoQ.isSuccess ? "success" : autoQ.isError ? "warning" : "neutral",
        errors: blocker || "0",
        recovery: blockCat || "Stable",
        detail: blocker
          ? `Mode: ${statusLabel(auto.ops_mode || execState.ops_mode, "LIVE")}${blocker ? ` · Blocker: ${blocker}` : ""}`
          : `Mode: ${statusLabel(auto.ops_mode || execState.ops_mode, "LIVE")}`,
      },
      {
        id: "oms",
        title: "OMS",
        status: omsLabel || "UNKNOWN",
        tone:
          omsStatus === "HEALTHY" || Boolean(execState.execution_enabled)
            ? "success"
            : omsStatus === "NOT_READY" || omsStatus === "DISABLED"
              ? "warning"
              : "neutral",
        errors: "0",
        recovery: "Stable",
        metrics: [
          { label: "Orders", value: String(session.orders.length) },
          { label: "Positions", value: String(openN) },
        ],
      },
      {
        id: "risk",
        title: "Risk Engine",
        status: riskClear ? "ACTIVE" : blockCat,
        tone: riskClear ? "success" : "warning",
        errors: riskClear ? "0" : blockCat,
        recovery: riskClear ? "Stable" : "Gating",
        detail: riskClear
          ? "Risk gates active — no bypass"
          : blocker
            ? `Gating: ${blocker}`
            : undefined,
      },
      {
        id: "pme",
        title: "PME",
        status: pmeLabel,
        tone: openN === 0 ? "neutral" : "success",
        errors: "0",
        recovery: "Stable",
        detail: openN === 0 ? "No open positions — PME idle/synced" : undefined,
      },
      {
        id: "ai",
        title: "AI / ITE",
        status: aiStatus || (autoQ.isSuccess ? "HEALTHY" : "UNKNOWN"),
        tone: aiStatus === "HEALTHY" || autoQ.isSuccess ? "success" : "neutral",
        errors: "0",
        recovery: "Stable",
        detail: str(asRecord(components.ai).detail, "") || undefined,
      },
      {
        id: "portfolio",
        title: "Portfolio",
        status: openN > 0 ? "Open book" : "Flat",
        tone: openN > 0 ? "success" : "neutral",
        errors: "0",
        recovery: "Stable",
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
        heartbeat: signalsQ.dataUpdatedAt
          ? new Date(signalsQ.dataUpdatedAt).toISOString().slice(11, 19)
          : "—",
        errors: signalsQ.isError ? "Feed error" : "0",
        recovery: signalsQ.isError ? "Retrying poll" : "Stable",
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
    autoQ.dataUpdatedAt,
    autoQ.isError,
    autoQ.isSuccess,
    backendLatencyMs,
    backendQ.dataUpdatedAt,
    backendQ.isError,
    backendQ.isSuccess,
    components,
    componentsLatencyMs,
    dash,
    execState,
    facts,
    health,
    isAuthenticated,
    live,
    mt5,
    mt5Q.isError,
    mt5Q.isFetched,
    positions,
    session,
    signalsQ.dataUpdatedAt,
    signalsQ.isError,
    signalsQ.isSuccess,
    statuses,
    user,
    versionLabel,
    weltradeQ.isError,
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
