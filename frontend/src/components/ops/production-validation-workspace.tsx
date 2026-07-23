"use client";

import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import {
  executionApi,
  iteOpsApi,
  mt5Api,
} from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import {
  buildProductionValidationModel,
  type ValidationLight,
} from "@/lib/production-validation";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
  className,
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "border border-[var(--border)] bg-[var(--surface)]",
        className,
      )}
    >
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Row({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-[var(--border)]/60 py-1.5 last:border-0">
      <span className="text-[11px] uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
        {label}
      </span>
      <span
        className={cn(
          "max-w-[65%] truncate text-right font-mono text-[12px] text-[var(--fg)]",
          tone === "ok" && "text-[var(--success)]",
          tone === "warn" && "text-[var(--warning)]",
          tone === "bad" && "text-[var(--danger)]",
        )}
        title={value}
      >
        {value}
      </span>
    </div>
  );
}

function toneConn(v: string): string | undefined {
  const u = v.toUpperCase();
  if (u.includes("CONNECT") || u === "OK" || u === "LIVE" || u === "RUNNING" || u === "ENABLED") {
    return "ok";
  }
  if (u.includes("OFF") || u.includes("MISS") || u === "BLOCKED" || u === "ARMED") {
    return "bad";
  }
  return undefined;
}

function LightCard({ light }: { light: ValidationLight }) {
  return (
    <div
      className={cn(
        "border px-3 py-3",
        light.passed
          ? "border-[var(--success)] bg-[var(--success-soft)]"
          : "border-[var(--border)] bg-[var(--surface-2)]",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg)]">
          {light.label}
        </span>
        <Badge tone={light.passed ? "success" : "warning"}>
          {light.passed ? "GREEN" : "WAIT"}
        </Badge>
      </div>
      <p className="mt-2 text-[12px] text-[var(--fg-muted)]">{light.detail}</p>
    </div>
  );
}

export function ProductionValidationWorkspace() {
  const autoQ = useQuery({
    queryKey: ["ite-ops-auto-trading", "pv"],
    queryFn: iteOpsApi.autoTrading,
    retry: false,
    refetchInterval: 8_000,
  });
  const centerQ = useQuery({
    queryKey: ["ite-ops-center", "pv"],
    queryFn: iteOpsApi.controlCenter,
    retry: false,
    refetchInterval: 12_000,
  });
  const lrQ = useQuery({
    queryKey: ["ite-ops-launch-readiness", "pv"],
    queryFn: iteOpsApi.launchReadiness,
    retry: false,
    refetchInterval: 15_000,
  });
  const mt5Q = useQuery({
    queryKey: ["mt5-status", "pv"],
    queryFn: mt5Api.status,
    retry: false,
    refetchInterval: 10_000,
  });
  const tickQ = useQuery({
    queryKey: ["mt5-tick", TRADING_SYMBOL, "pv"],
    queryFn: () => mt5Api.tick(TRADING_SYMBOL),
    retry: false,
    refetchInterval: 3_000,
  });
  const journalQ = useQuery({
    queryKey: ["execution-journal", "pv"],
    queryFn: () => executionApi.journal(80),
    retry: false,
    refetchInterval: 10_000,
  });
  const auditsQ = useQuery({
    queryKey: ["execution-audits", "pv"],
    queryFn: () => executionApi.audits(80),
    retry: false,
    refetchInterval: 15_000,
  });
  const analyticsQ = useQuery({
    queryKey: ["execution-analytics", "pv"],
    queryFn: () => executionApi.analytics(120),
    retry: false,
    refetchInterval: 30_000,
  });

  const loading = autoQ.isLoading || centerQ.isLoading;
  const err = autoQ.error || centerQ.error;

  if (loading && !autoQ.data) {
    return <DeskSkeleton rows={8} />;
  }
  if (err && !autoQ.data) {
    return (
      <DeskError
        message={err instanceof Error ? err.message : "Failed to load live status"}
      />
    );
  }

  const model = buildProductionValidationModel({
    autoTrading: autoQ.data,
    controlCenter: centerQ.data,
    launchReadiness: lrQ.data,
    mt5Status: mt5Q.data,
    tick: tickQ.data,
    journal: journalQ.data,
    audits: auditsQ.data,
    analytics: analyticsQ.data,
  });

  const { system, market, strategy, decision, risk, safety, execution, journal, stats, lights } =
    model;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <BadgeCheck className="h-4 w-4 text-[var(--fg-subtle)]" />
        <span className="text-[12px] font-medium text-[var(--fg)]">
          Production Validation
        </span>
        <Badge tone={model.productionReady ? "success" : "warning"}>
          {model.productionReady ? "PRODUCTION READY" : "VALIDATING"}
        </Badge>
        <Badge tone={model.modesAligned ? "success" : "warning"}>
          UI↔API {model.modesAligned ? "SYNC" : "DRIFT"} · {system.opsMode}
        </Badge>
        <span className="ml-auto text-[11px] text-[var(--fg-subtle)]">
          Live polls · never mutates trading rules
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {lights.map((light) => (
          <LightCard key={light.key} light={light} />
        ))}
      </div>

      <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
        <Panel title="System">
          <Row label="Ops Mode" value={system.opsMode} tone={toneConn(system.opsMode)} />
          <Row label="Auto Trading" value={system.autoTrading} tone={toneConn(system.autoTrading)} />
          <Row label="Gateway" value={system.gateway} tone={toneConn(system.gateway)} />
          <Row label="MT5" value={system.mt5} tone={toneConn(system.mt5)} />
          <Row label="Broker" value={system.broker} tone={toneConn(system.broker)} />
          <Row label="Snapshot" value={system.snapshot} tone={toneConn(system.snapshot)} />
          <Row
            label="Session"
            value={`${system.session}${system.sessionAllowed ? " · allowed" : " · blocked"}`}
            tone={system.sessionAllowed ? "ok" : "warn"}
          />
          <Row
            label="Persistence"
            value={
              system.durable
                ? `DURABLE · ${system.hydrateSource} · ${system.persistedMode}`
                : `EPHEMERAL · ${system.hydrateSource}`
            }
            tone={system.durable ? "ok" : "warn"}
          />
        </Panel>

        <Panel title="Market">
          <Row label="Symbol" value={market.symbol} />
          <Row label="Bid" value={market.bid} />
          <Row label="Ask" value={market.ask} />
          <Row label="Spread" value={market.spread} />
          <Row label="Last Tick" value={market.lastTick} />
          <Row label="Snapshot Age" value={market.snapshotAge} />
        </Panel>

        <Panel title="Strategy">
          <Row label="Signal ID" value={strategy.signalId} />
          <Row label="Quality" value={strategy.quality} />
          <Row label="Confluence" value={strategy.confluence} />
          <Row label="Trend" value={strategy.trend} />
          <Row label="Regime / Session" value={`${strategy.regime} / ${strategy.session}`} />
        </Panel>

        <Panel title="Decision">
          <Row label="Decision" value={decision.decision} />
          <Row label="Reason" value={decision.reason} tone="warn" />
          <Row label="Confidence" value={decision.confidence} />
          <Row
            label="Forwarded to OMS"
            value={decision.forwardedToOms}
            tone={decision.forwardedToOms === "YES" ? "ok" : undefined}
          />
          <Row label="Cycle Outcome" value={decision.cycleOutcome} />
          {decision.reasons.length > 0 ? (
            <ul className="mt-2 max-h-28 space-y-1 overflow-auto text-[11px] text-[var(--fg-muted)]">
              {decision.reasons.slice(0, 8).map((r) => (
                <li key={r}>· {r}</li>
              ))}
            </ul>
          ) : null}
        </Panel>

        <Panel title="Risk">
          <Row label="Position Size" value={risk.positionSize} />
          <Row label="Daily Risk" value={risk.dailyRisk} />
          <Row label="Exposure" value={risk.exposure} />
          <Row label="Result" value={risk.result} />
        </Panel>

        <Panel title="Safety">
          <Row
            label="Status"
            value={safety.status}
            tone={safety.status === "BLOCKED" ? "bad" : "ok"}
          />
          <Row label="Kill Switch" value={safety.killSwitch} tone={toneConn(safety.killSwitch)} />
          <Row label="Exact Block Reason" value={safety.blockReason} tone="warn" />
        </Panel>

        <Panel title="Execution">
          <Row label="OMS Request" value={execution.omsRequest} />
          <Row label="Broker Response" value={execution.brokerResponse} />
          <Row label="MT5 Ticket" value={execution.mt5Ticket} tone={execution.mt5Ticket !== "—" ? "ok" : undefined} />
          <Row label="Deal ID" value={execution.dealId} />
          <Row label="Fill Price" value={execution.fillPrice} />
          <Row label="Latency" value={execution.latency} />
        </Panel>

        <Panel title="Journal">
          <Row label="Last Event" value={journal.lastEvent} />
          <Row label="Last Trade" value={journal.lastTrade} />
          <Row label="Last Rejection" value={journal.lastRejection} tone="warn" />
          <Row label="Timestamp" value={journal.timestamp} />
        </Panel>

        <Panel title="Statistics · Today" className="xl:col-span-1">
          <div className="grid grid-cols-2 gap-x-4">
            <Row label="Signals" value={String(stats.signalsGenerated)} />
            <Row label="Rejected" value={String(stats.signalsRejected)} />
            <Row label="Risk Rejects" value={String(stats.riskRejects)} />
            <Row label="Safety Rejects" value={String(stats.safetyRejects)} />
            <Row label="OMS Requests" value={String(stats.omsRequests)} />
            <Row label="Broker Requests" value={String(stats.brokerRequests)} />
            <Row label="MT5 Orders" value={String(stats.mt5Orders)} />
            <Row label="Filled" value={String(stats.filledTrades)} />
            <Row label="Win Rate" value={stats.winRate} />
            <Row label="Avg Latency" value={stats.averageLatency} />
          </div>
        </Panel>
      </div>

      <Panel title="Operator note">
        <div className="flex gap-2 text-[12px] text-[var(--fg-muted)]">
          <Shield className="mt-0.5 h-4 w-4 shrink-0 text-[var(--fg-subtle)]" />
          <p>
            Read-only validation desk. Displays live Auto Trading / Control Center / MT5 /
            Journal evidence only. Does not change Risk, Safety, sessions, quality gates, or
            inject trades. Current Launch Lock Ops Mode:{" "}
            <span className="font-mono text-[var(--fg)]">
              {str(asRecord(lrQ.data).ops_mode, model.lrOpsMode)}
            </span>
            .
          </p>
        </div>
      </Panel>
    </div>
  );
}
