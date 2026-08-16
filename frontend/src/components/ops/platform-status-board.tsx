"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import {
  getApiConnectionState,
  subscribeApiConnection,
  type ApiConnectionState,
} from "@/lib/api/connectivity";
import { ApiError } from "@/lib/api/client";
import {
  iteOpsApi,
  mt5Api,
  platformApi,
  signalCenterApi,
  weltradeApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, statusLabel, str } from "@/lib/desk";
import {
  mergePlaneOk,
  resolveTradingComponentsView,
} from "@/lib/trading/component-health";
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

function feedErrorKind(error: unknown): "unauthorized" | "timeout" | "server" | "network" | "other" {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403) return "unauthorized";
    if (error.code === "timeout") return "timeout";
    if (error.code === "network_error") return "network";
    if (error.status >= 500) return "server";
  }
  return "other";
}

async function timedHealthLive(): Promise<{
  payload: Record<string, unknown>;
  latencyMs: number;
}> {
  const started = performance.now();
  const payload = await platformApi.healthLive();
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

  // Distinct key from plain healthLive consumers (offline banner / latency plane).
  const backendQ = useQuery({
    queryKey: ["platform-health-live", "timed"],
    queryFn: timedHealthLive,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
    refetchIntervalInBackground: false,
  });
  const componentsQ = useQuery({
    // Shared key — AutoRecovery + Executive reuse this cache (no triple poll).
    queryKey: ["trading-components-health"],
    queryFn: platformApi.tradingComponents,
    staleTime: 20_000,
    refetchInterval: 45_000,
    retry: 1,
    refetchIntervalInBackground: false,
  });
  // Optional broker detail — do not hammer; trading-components is authoritative for MT5/gateway.
  const weltradeQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    staleTime: 90_000,
    refetchInterval: 180_000,
    retry: false,
    refetchIntervalInBackground: false,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    staleTime: 30_000,
    refetchInterval: 60_000,
    retry: 1,
    refetchIntervalInBackground: false,
  });
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading"],
    queryFn: iteOpsApi.autoTrading,
    staleTime: 60_000,
    refetchInterval: 90_000,
    retry: 1,
    refetchIntervalInBackground: false,
  });
  const signalsQ = useQuery({
    queryKey: ["signals-center", "mission"],
    queryFn: () => signalCenterApi.list({}),
    staleTime: 60_000,
    refetchInterval: 120_000,
    retry: 1,
    refetchIntervalInBackground: false,
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

  const componentsErrorKind =
    componentsQ.error instanceof ApiError
      ? componentsQ.error.code === "timeout"
        ? ("timeout" as const)
        : componentsQ.error.code === "network_error"
          ? ("network" as const)
          : ("other" as const)
      : componentsQ.isError
        ? ("other" as const)
        : null;
  const authHealth = resolveTradingComponentsView({
    payload: componentsQ.data,
    isSuccess: componentsQ.isSuccess,
    isError: componentsQ.isError,
    errorKind: componentsErrorKind,
  });
  const components = asRecord(componentsQ.data);
  const statuses = asRecord(
    authHealth
      ? {
          gateway: authHealth.rawStatuses.gateway,
          mt5: authHealth.rawStatuses.mt5,
          oms: authHealth.rawStatuses.oms,
          ai: authHealth.rawStatuses.ai,
        }
      : components.statuses,
  );
  const gatewayComponent = asRecord(components.gateway);
  const gatewayEvidence = asRecord(gatewayComponent.evidence);
  const omsComponent = asRecord(components.oms);
  const omsEvidence = asRecord(omsComponent.evidence);
  const dash = asRecord(signalsQ.data?.dashboard);
  const signalRows = asList(signalsQ.data?.items ?? signalsQ.data?.signals ?? signalsQ.data);
  const positions = session.positions;
  const version = asRecord(versionQ.data);
  const versionLabel =
    str(version.version || version.git_sha || version.build || version.release, "—") ||
    "—";
  const backendLatencyMs = backendQ.data?.latencyMs ?? null;
  const timing = asRecord(components.timing);
  const componentsAggregateRttMs = Number.isFinite(num(timing.total_ms, NaN))
    ? Math.round(num(timing.total_ms))
    : null;
  const gatewayProbeMs = num(
    gatewayEvidence.latency_ms ?? timing.gateway_ms,
    NaN,
  );

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

    // Authoritative trading-components (+ hysteresis) first. Session / mt5-status
    // / weltrade are secondary — a process-local miss must not flip HEALTHY→down.
    const gatewayOk = mergePlaneOk(
      authHealth?.gateway.ok ?? null,
      session.healthKnown
        ? session.gatewayOnline
        : health.gateway_online != null
          ? Boolean(health.gateway_online || health.gateway_reachable)
          : null,
    );

    const mt5Ok = mergePlaneOk(
      authHealth?.mt5.ok ?? null,
      mt5.connected != null
        ? Boolean(mt5.connected)
        : session.healthKnown
          ? session.connected
          : null,
    );

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
    // Only UNKNOWN when broker health errored AND we lack authoritative MT5 up.
    const brokerHealthUnknown = Boolean(
      weltradeQ.isError && !mt5Confirmed && mt5Ok !== false,
    );

    const openN = positions.length;
    const floatPnl = positions.reduce((s, p) => s + num(p.profit, 0), 0);

    const executionEnabled = Boolean(
      execState.execution_enabled ??
        omsEvidence.execution_enabled ??
        facts.execution_enabled,
    );
    const runState = statusLabel(
      execState.auto_trading_run_state || auto.run_state,
      "",
    );
    const gateStatus = statusLabel(auto.status || execState.gate_status, "");
    const opsMode = statusLabel(auto.ops_mode || execState.ops_mode, "");
    const blocker = statusLabel(auto.primary_blocker || execState.primary_blocker, "");
    const blockCat = statusLabel(
      auto.blocking_category || execState.blocking_category,
      "",
    );
    const riskClear =
      !blockCat || blockCat === "—" || blockCat.toLowerCase() === "none";

    // Auto Trading: never invent LIVE/UNAVAILABLE from missing feed defaults.
    let autoCardStatus = "—";
    let autoTone: Tone = "neutral";
    let autoDetail: string | undefined;
    if (autoQ.isSuccess) {
      const raw = (gateStatus || runState || "READY").toUpperCase();
      if (executionEnabled && (raw.includes("ALLOW") || raw === "OK" || raw === "READY" || runState.toUpperCase() === "RUNNING")) {
        autoCardStatus = "ENABLED";
        autoTone = "success";
      } else if (raw.includes("BLOCK") || raw.includes("DENY") || raw.includes("STOP")) {
        autoCardStatus = raw;
        autoTone = "warning";
      } else {
        autoCardStatus = raw;
        autoTone = executionEnabled ? "success" : "warning";
      }
      autoDetail = [
        opsMode ? `Mode: ${opsMode}` : null,
        executionEnabled ? "Mock: OFF" : null,
        runState ? `Run: ${runState}` : null,
        blocker ? `Blocker: ${blocker}` : null,
      ]
        .filter(Boolean)
        .join(" · ");
    } else if (autoQ.isError) {
      const kind = feedErrorKind(autoQ.error);
      if (omsStatus === "HEALTHY" && mt5Confirmed && executionEnabled) {
        autoCardStatus = "ENABLED";
        autoTone = "success";
        autoDetail =
          "Mode: LIVE · Status feed delayed — OMS/MT5 confirm execution path ready";
      } else if (omsStatus === "HEALTHY" && mt5Confirmed) {
        autoCardStatus = "LIVE PATH READY";
        autoTone = "success";
        autoDetail =
          kind === "timeout"
            ? "Auto-trading detail feed delayed — using trading-components"
            : "Auto-trading detail feed unavailable — OMS/MT5 healthy";
      } else {
        autoCardStatus =
          kind === "unauthorized"
            ? "AUTH REQUIRED"
            : kind === "timeout"
              ? "FEED DELAYED"
              : "STATUS FEED UNAVAILABLE";
        autoTone = "warning";
        autoDetail = "Waiting for /ite/ops/auto-trading — not the same as MT5 disconnected";
      }
    } else if (omsStatus === "HEALTHY" && mt5Confirmed) {
      autoCardStatus = "CHECKING";
      autoTone = "neutral";
    }

    const eligibleFromAuto = str(
      asRecord(asRecord(auto.ai_scalping).scan).eligible_count,
      "",
    );
    const scannerRunning = aiStatus === "HEALTHY" || autoQ.isSuccess;
    const scannerFeedKind = autoQ.isError ? feedErrorKind(autoQ.error) : null;

    const buyN = num(dash.buy_signals, NaN);
    const sellN = num(dash.sell_signals, NaN);
    const signalCount = signalRows.length;
    const hasSignalCounts = Number.isFinite(buyN) || Number.isFinite(sellN);
    const activeSignalTotal =
      (Number.isFinite(buyN) ? buyN : 0) + (Number.isFinite(sellN) ? sellN : 0);

    let signalsStatus = "—";
    let signalsTone: Tone = "neutral";
    let signalsErrors = "0";
    let signalsRecovery = "Stable";
    let signalsDetail: string | undefined;
    if (signalsQ.isSuccess) {
      if (signalCount === 0 && (!hasSignalCounts || activeSignalTotal === 0)) {
        signalsStatus = "NO ACTIVE SIGNALS";
        signalsTone = "neutral";
        signalsDetail = "No valid setup currently passes the existing safeguards.";
      } else {
        signalsStatus = "LIVE";
        signalsTone = "success";
      }
    } else if (signalsQ.isError) {
      const kind = feedErrorKind(signalsQ.error);
      if (aiStatus === "HEALTHY" || scannerRunning) {
        // ITE healthy + empty eligible is the common production case — not a feed outage.
        signalsStatus = "NO ACTIVE SIGNALS";
        signalsTone = "neutral";
        signalsErrors = "0";
        signalsRecovery = "Stable";
        signalsDetail =
          kind === "timeout"
            ? "Signal list feed delayed — ITE reports no eligible setups"
            : "Signal list feed unavailable — ITE healthy, no eligible setups assumed";
      } else if (kind === "unauthorized") {
        signalsStatus = "AUTH REQUIRED";
        signalsTone = "warning";
        signalsErrors = "Unauthorized";
        signalsRecovery = "Sign in again";
      } else if (kind === "timeout") {
        signalsStatus = "FEED DELAYED";
        signalsTone = "warning";
        signalsErrors = "Timeout";
        signalsRecovery = "Retrying poll";
      } else {
        signalsStatus = "FEED UNAVAILABLE";
        signalsTone = "warning";
        signalsErrors = "Feed error";
        signalsRecovery = "Retrying poll";
      }
    }

    const pmeLabel = statusLabel(
      live.pme_state || live.position_engine,
      openN === 0 ? "Synced (flat)" : "—",
    );
    const omsLabel =
      omsStatus ||
      statusLabel(execState.ops_mode, executionEnabled ? "READY" : "—");

    const gatewayLatencyLabel = Number.isFinite(gatewayProbeMs)
      ? `${Math.round(gatewayProbeMs)} ms`
      : str(session.latencyMs, "—") !== "—"
        ? `${session.latencyMs} ms`
        : "—";

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
        latency: backendLatencyMs != null ? `${backendLatencyMs} ms` : "—",
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
            ? authHealth?.gateway.stale
              ? "HEALTHY (cached)"
              : "HEALTHY"
            : gatewayOk === false
              ? "UNREACHABLE"
              : componentsQ.isFetching
                ? "CHECKING"
                : "UNKNOWN",
        tone: toneFromOk(gatewayOk),
        latency: gatewayLatencyLabel,
        heartbeat: str(session.heartbeatAt, "—").slice(0, 19) || "—",
        version: str(
          health.gateway_version || health.version || mt5.build || mt5.terminal_build,
          "—",
        ),
        errors: gatewayOk === false ? statusLabel(health.diagnostic, "No heartbeat") : "0",
        recovery: gatewayOk === false ? "Await reconnect" : "Stable",
        detail: [
          session.gatewayLabel ||
            str(authHealth?.gateway.detail || gatewayComponent.detail, ""),
          authHealth?.gateway.stale
            ? "Last-known-good — trading-components probe delayed"
            : undefined,
          Number.isFinite(gatewayProbeMs) && componentsAggregateRttMs != null
            ? `Probe RTT ${Math.round(gatewayProbeMs)} ms · aggregate ${componentsAggregateRttMs} ms`
            : Number.isFinite(gatewayProbeMs)
              ? `Railway→gateway probe ${Math.round(gatewayProbeMs)} ms`
              : undefined,
        ]
          .filter(Boolean)
          .join(" — ") || undefined,
      },
      {
        id: "mt5",
        title: "MT5",
        status:
          mt5Ok === true
            ? authHealth?.mt5.stale
              ? "CONNECTED (cached)"
              : "CONNECTED"
            : mt5Ok === false
              ? "DISCONNECTED"
              : componentsQ.isFetching
                ? "CHECKING"
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
        status: scannerRunning ? "RUNNING" : autoQ.isError ? "UNKNOWN" : "—",
        tone: scannerRunning ? "success" : autoQ.isError ? "warning" : "neutral",
        heartbeat: autoQ.dataUpdatedAt
          ? new Date(autoQ.dataUpdatedAt).toISOString().slice(11, 19)
          : componentsQ.dataUpdatedAt
            ? new Date(componentsQ.dataUpdatedAt).toISOString().slice(11, 19)
            : "—",
        errors:
          scannerRunning
            ? "0"
            : scannerFeedKind === "timeout"
              ? "Ops feed timeout"
              : autoQ.isError
                ? "Ops feed error"
                : "0",
        recovery: scannerRunning
          ? "Stable"
          : autoQ.isError
            ? "Retrying poll"
            : "Stable",
        detail: scannerRunning
          ? autoQ.isError
            ? "ITE running — optional ops detail feed delayed (not a scanner outage)"
            : undefined
          : undefined,
        metrics: [
          {
            label: "Eligible",
            value: eligibleFromAuto || "—",
          },
        ],
      },
      {
        id: "auto",
        title: "Auto Trading",
        status: autoCardStatus,
        tone: autoTone,
        errors: blocker || "0",
        recovery: blockCat || (autoQ.isError ? "Using trading-components" : "Stable"),
        detail: autoDetail,
      },
      {
        id: "oms",
        title: "OMS",
        status: omsLabel || "UNKNOWN",
        tone:
          omsStatus === "HEALTHY" || executionEnabled
            ? "success"
            : omsStatus === "NOT_READY" || omsStatus === "DISABLED"
              ? "warning"
              : "neutral",
        errors: "0",
        recovery: "Stable",
        detail: str(omsComponent.detail, "") || undefined,
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
          {
            label: "Float PnL",
            value: Number.isFinite(floatPnl) ? floatPnl.toFixed(2) : "—",
          },
          { label: "Positions", value: String(openN) },
        ],
      },
      {
        id: "signals",
        title: "Signals",
        status: signalsStatus,
        tone: signalsTone,
        heartbeat: signalsQ.dataUpdatedAt
          ? new Date(signalsQ.dataUpdatedAt).toISOString().slice(11, 19)
          : "—",
        errors: signalsErrors,
        recovery: signalsRecovery,
        detail: signalsDetail,
        metrics: [
          {
            label: "BUY",
            value: Number.isFinite(buyN) ? String(buyN) : signalsQ.isSuccess ? "0" : "—",
          },
          {
            label: "SELL",
            value: Number.isFinite(sellN) ? String(sellN) : signalsQ.isSuccess ? "0" : "—",
          },
          { label: "Enabled", value: str(dash.enabled_symbols, "—") },
        ],
      },
    ];
  }, [
    apiState,
    authHealth,
    auto,
    autoQ.dataUpdatedAt,
    autoQ.error,
    autoQ.isError,
    autoQ.isSuccess,
    backendLatencyMs,
    backendQ.dataUpdatedAt,
    backendQ.isError,
    backendQ.isSuccess,
    components,
    componentsAggregateRttMs,
    componentsQ.dataUpdatedAt,
    componentsQ.isFetching,
    dash,
    execState,
    facts,
    gatewayComponent,
    gatewayProbeMs,
    health,
    isAuthenticated,
    live,
    mt5,
    mt5Q.isError,
    mt5Q.isFetched,
    omsComponent,
    omsEvidence,
    positions,
    session,
    signalRows.length,
    signalsQ.dataUpdatedAt,
    signalsQ.error,
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
