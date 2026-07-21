"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Gauge, Radio, Server } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton, DeskTable } from "@/components/desk/primitives";
import { WeltradeGatewayStatus } from "@/components/desk/weltrade-gateway-status";
import { ExecutionMetricsStrip } from "@/components/execution/execution-metrics-strip";
import { ExecutionDiagnosticsPanel } from "@/components/execution/execution-diagnostics";
import { latestSuccessfulExecution } from "@/lib/execution/ops-metrics";
import { loadLastExecutionMetrics } from "@/lib/execution/last-metrics";
import {
  executionApi,
  mt5Api,
  platformApi,
  weltradeApi,
} from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { formatNumber } from "@/lib/utils";
import { useTradingSession } from "@/providers/trading-session-provider";

const IteReliabilityPanel = dynamic(
  () =>
    import("@/components/ops/ite-reliability-panel").then(
      (m) => m.IteReliabilityPanel,
    ),
  { ssr: false, loading: () => <DeskSkeleton rows={4} /> },
);

function Panel({
  title,
  icon: Icon,
  children,
  action,
}: {
  title: string;
  icon: typeof Gauge;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="flex items-center justify-between gap-2 border-b border-[var(--border)] px-3 py-2">
        <div className="flex items-center gap-2">
          <Icon className="h-3.5 w-3.5 text-[var(--fg-subtle)]" aria-hidden />
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            {title}
          </h2>
        </div>
        {action}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-2.5">
      <p className="text-[9px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">{label}</p>
      <p className="mt-1 font-mono text-sm tabular text-[var(--fg)]">{value}</p>
      {hint ? <p className="mt-0.5 text-[10px] text-[var(--fg-muted)]">{hint}</p> : null}
    </div>
  );
}

function fmtMs(v: unknown): string {
  const n = num(v);
  return Number.isFinite(n) ? `${formatNumber(n, 0)} ms` : "—";
}

/**
 * Production Operations Dashboard — Monitoring workspace.
 * Live execution metrics, platform health, gateway, reliability, diagnostics.
 */
export function ProductionOpsDashboard() {
  const session = useTradingSession();

  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
    refetchInterval: 15_000,
  });
  const mt5 = useQuery({
    queryKey: ["mt5-status"],
    queryFn: mt5Api.status,
    retry: false,
    refetchInterval: 10_000,
  });
  const weltrade = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    retry: false,
    refetchInterval: 10_000,
  });
  const journal = useQuery({
    queryKey: ["execution-journal", "ops"],
    queryFn: () => executionApi.journal(40),
    retry: false,
    refetchInterval: 8_000,
  });
  const audits = useQuery({
    queryKey: ["execution-audits", "ops"],
    queryFn: () => executionApi.audits(80),
    retry: false,
    refetchInterval: 8_000,
  });
  const analytics = useQuery({
    queryKey: ["execution-analytics", "ops"],
    queryFn: () => executionApi.analytics(100),
    retry: false,
    refetchInterval: 15_000,
  });

  const latest = useMemo(
    () =>
      latestSuccessfulExecution({
        journalItems: journal.data,
        auditItems: audits.data,
        sessionFallback: loadLastExecutionMetrics(),
      }),
    [journal.data, audits.data],
  );

  const deps = asList(asRecord(health.data).dependencies).map(asRecord);
  const findDep = (name: string) =>
    deps.find((d) => str(d.name).toLowerCase().includes(name.toLowerCase()));
  const db = findDep("postgres") || findDep("database");
  const redis = findDep("redis");
  const mt = asRecord(mt5.data);
  const wt = asRecord(weltrade.data);
  const metricsBody = asRecord(asRecord(analytics.data).metrics);
  const recentJournal = asList(asRecord(journal.data).items ?? journal.data)
    .map(asRecord)
    .slice(0, 8);

  return (
    <div className="space-y-3">
      <WeltradeGatewayStatus />

      <Panel
        title="Live execution metrics"
        icon={Activity}
        action={
          latest ? (
            <Badge tone="success">Last fill</Badge>
          ) : (
            <Badge tone="neutral">No fills</Badge>
          )
        }
      >
        {journal.isLoading && !latest ? (
          <DeskSkeleton rows={2} />
        ) : journal.isError && !latest ? (
          <DeskError
            message="Unable to load execution journal."
            onRetry={() => void journal.refetch()}
          />
        ) : (
          <>
            <ExecutionMetricsStrip
              metrics={
                latest?.metrics ?? {
                  signalMs: null,
                  riskMs: null,
                  safetyMs: null,
                  orderCheckMs: null,
                  brokerFillMs: null,
                  totalMs: null,
                  slippage: null,
                  spread: null,
                  fillStatus: null,
                  source: "none",
                }
              }
            />
            {latest ? (
              <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
                <Kpi label="Symbol" value={latest.symbol || "—"} />
                <Kpi label="Side" value={(latest.side || "—").toUpperCase()} />
                <Kpi label="Volume" value={latest.volume || "—"} />
                <Kpi label="Fill price" value={latest.price || "—"} />
                <Kpi label="MT5 ticket" value={latest.ticket || "—"} />
                <Kpi label="Deal ID" value={latest.deal || "—"} />
              </div>
            ) : (
              <p className="mt-3 text-sm text-[var(--fg-muted)]">
                Complete a live XAUUSD fill to populate Signal → Risk → Safety → Order Check →
                Broker Fill timings here. Metrics never invent values.
              </p>
            )}
          </>
        )}
      </Panel>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label="API"
          value={str(asRecord(health.data).status, "—")}
          hint={str(asRecord(health.data).environment)}
        />
        <Kpi
          label="Broker / MT5"
          value={
            mt.connected || session.connected
              ? "connected"
              : mt5.isError
                ? "error"
                : "disconnected"
          }
          hint={fmtMs(mt.latency_ms ?? session.latencyMs)}
        />
        <Kpi label="Database" value={str(db?.status, "—")} hint={fmtMs(db?.latency_ms)} />
        <Kpi label="Redis" value={str(redis?.status, "—")} hint={fmtMs(redis?.latency_ms)} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Platform pulse" icon={Server}>
          <div className="grid grid-cols-2 gap-2">
            <Kpi
              label="Gateway"
              value={
                session.gatewayOnline || wt.gateway_online ? "online" : "offline"
              }
            />
            <Kpi
              label="Execution"
              value={wt.execution_enabled ? "enabled" : "disabled"}
            />
            <Kpi label="Login" value={str(mt.login ?? session.login, "—")} />
            <Kpi label="Server" value={str(mt.server ?? session.server, "—")} />
            <Kpi
              label="Fill rate"
              value={
                metricsBody.fill_rate != null
                  ? formatNumber(num(metricsBody.fill_rate) * 100, 0) + "%"
                  : "—"
              }
            />
            <Kpi
              label="Avg latency"
              value={
                metricsBody.latency_ms_avg != null
                  ? fmtMs(metricsBody.latency_ms_avg)
                  : latest?.metrics.totalMs != null
                    ? fmtMs(latest.metrics.totalMs)
                    : "—"
              }
            />
          </div>
        </Panel>

        <Panel
          title="Recent executions"
          icon={Radio}
          action={
            <Button asChild size="sm" variant="ghost">
              <Link href="/execution/diagnostics">Audit trail</Link>
            </Button>
          }
        >
          {recentJournal.length === 0 ? (
            <p className="text-sm text-[var(--fg-muted)]">No journal rows yet.</p>
          ) : (
            <DeskTable
              columns={["Time", "Symbol", "Result", "Ticket", "Latency"]}
              rows={recentJournal.map((r) => [
                str(r.timestamp || r.submitted_at, "—").replace("T", " ").slice(0, 19),
                str(r.symbol, "—"),
                str(r.execution_result || r.outcome, "—"),
                str(r.ticket ?? r.order_id, "—"),
                fmtMs(r.latency_ms),
              ])}
            />
          )}
        </Panel>
      </div>

      <Panel title="Execution diagnostics" icon={Activity}>
        <ExecutionDiagnosticsPanel />
      </Panel>

      <IteReliabilityPanel />
    </div>
  );
}
