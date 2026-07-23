"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function statusTone(status: string): "success" | "warning" | "danger" | "neutral" {
  const s = status.toUpperCase();
  if (s === "PASS" || s === "GREEN") return "success";
  if (s === "WARNING" || s === "YELLOW") return "warning";
  if (s === "FAIL" || s === "RED" || s === "CRITICAL") return "danger";
  return "neutral";
}

function fmt(v: unknown, d = 2): string {
  const n = num(v, NaN);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(d);
}

function KpiBar({ label, value }: { label: string; value: number }) {
  const tone = value >= 75 ? "bg-[var(--success)]" : value >= 55 ? "bg-[var(--warning)]" : "bg-[var(--danger)]";
  return (
    <div>
      <div className="mb-1 flex justify-between text-[11px] text-[var(--fg-muted)]">
        <span>{label}</span>
        <span className="font-mono tabular-nums">{Number.isFinite(value) ? value.toFixed(1) : "—"}</span>
      </div>
      <div className="h-1.5 w-full bg-[var(--surface-2)]">
        <div
          className={cn("h-full transition-all duration-200", tone)}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
          role="progressbar"
          aria-valuenow={Number.isFinite(value) ? value : 0}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={label}
        />
      </div>
    </div>
  );
}

export function InstitutionalControlCenterWorkspace() {
  const [query, setQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [focus, setFocus] = useState<string>("kpis");

  const q = useQuery({
    queryKey: ["ops", "institutional-control-center"],
    queryFn: () => iteOpsApi.institutionalControlCenter(),
    refetchInterval: 15_000,
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        document.getElementById("icc-search")?.focus();
      }
      if (e.key === "1") setFocus("system");
      if (e.key === "2") setFocus("live");
      if (e.key === "3") setFocus("portfolio");
      if (e.key === "4") setFocus("research");
      if (e.key === "5") setFocus("alerts");
      if (e.key === "r" || e.key === "R") void q.refetch();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [q]);

  const root = asRecord(q.data);
  const sections = asRecord(root.sections);
  const system = asRecord(sections.system_status);
  const subsystems = asList(system.subsystems).map(asRecord);
  const qv = query.trim().toLowerCase();
  const filteredSubs = !qv
    ? subsystems
    : subsystems.filter((s) =>
        `${str(s.name)} ${str(s.detail)} ${str(s.status)}`.toLowerCase().includes(qv),
      );

  if (q.isLoading) return <DeskSkeleton rows={10} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Institutional Control Center unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const live = asRecord(sections.live_trading);
  const portfolio = asRecord(sections.portfolio);
  const research = asRecord(sections.research);
  const analytics = asRecord(sections.analytics);
  const warehouse = asRecord(sections.data_warehouse);
  const alertsSec = asRecord(sections.alerts);
  const timeline = asRecord(sections.operational_timeline);
  const kpis = asRecord(sections.executive_kpis ?? root.executive_kpis);
  const architecture = asRecord(sections.architecture);

  const alerts = asList(alertsSec.alerts)
    .map(asRecord)
    .filter((a) => {
      if (severityFilter === "ALL") return true;
      return str(a.severity).toUpperCase() === severityFilter.toUpperCase();
    })
    .filter((a) => {
      if (!query.trim()) return true;
      const blob = `${str(a.message)} ${str(a.category)} ${str(a.severity)}`.toLowerCase();
      return blob.includes(query.trim().toLowerCase());
    });
  const events = asList(timeline.events)
    .map(asRecord)
    .filter((e) => {
      if (!query.trim()) return true;
      const blob = `${str(e.kind)} ${str(e.detail)}`.toLowerCase();
      return blob.includes(query.trim().toLowerCase());
    });
  const board = asList(research.leaderboard_top5).map(asRecord);
  const desks = asList(analytics.desks).map(asRecord);
  const archNodes = asList(architecture.nodes).map(asRecord);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">INSTITUTIONAL CONTROL CENTER</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">NEVER INFLUENCES TRADING</Badge>
        <Badge tone={statusTone(str(root.system_overall, "WARNING"))}>
          SYSTEM {str(root.system_overall, "—")}
        </Badge>
        <Button size="sm" variant="secondary" onClick={() => void q.refetch()}>
          Refresh (R)
        </Button>
      </div>

      <p className="text-[11px] text-[var(--fg-subtle)]">
        Executive cockpit — aggregates subsystems only. Shortcuts: / search · 1
        system · 2 live · 3 portfolio · 4 research · 5 alerts · R refresh.
      </p>

      <div className="flex flex-wrap gap-2">
        <input
          id="icc-search"
          aria-label="Search control center"
          className="min-w-[220px] flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px] text-[var(--fg)]"
          placeholder="Search alerts, timeline, subsystems…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          aria-label="Alert severity filter"
          className="border border-[var(--border)] bg-[var(--surface)] px-2 py-2 text-[12px]"
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
        >
          {["ALL", "Critical", "High", "Medium", "Low"].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <OpsPanel title="Executive KPIs">
        <div
          className={cn("grid gap-3 sm:grid-cols-2 lg:grid-cols-3", focus === "kpis" && "ring-1 ring-[var(--border-strong)]")}
        >
          <KpiBar label="Overall Platform Health" value={num(kpis.overall_platform_health, 0)} />
          <KpiBar label="Trading Readiness" value={num(kpis.trading_readiness, 0)} />
          <KpiBar label="Operational Stability" value={num(kpis.operational_stability, 0)} />
          <KpiBar label="Research Progress" value={num(kpis.research_progress, 0)} />
          <KpiBar label="Data Integrity" value={num(kpis.data_integrity, 0)} />
          <KpiBar label="System Availability" value={num(kpis.system_availability, 0)} />
        </div>
      </OpsPanel>

      <OpsPanel title="System status">
        <div
          id="icc-system"
          className={cn("grid gap-2 sm:grid-cols-2 lg:grid-cols-3", focus === "system" && "ring-1 ring-[var(--border-strong)]")}
        >
          {filteredSubs.map((s) => (
            <Link
              key={str(s.name)}
              href={str(s.href, "/ops")}
              className="border border-[var(--border)] px-3 py-2 hover:bg-[var(--surface-2)]/50"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="text-[13px] text-[var(--fg)]">{str(s.name)}</span>
                <Badge tone={statusTone(str(s.status))}>{str(s.status)}</Badge>
              </div>
              <p className="mt-1 font-mono text-[11px] text-[var(--fg-subtle)]">
                {str(s.detail, "—")}
              </p>
            </Link>
          ))}
        </div>
      </OpsPanel>

      <div className="grid gap-4 lg:grid-cols-2">
        <OpsPanel title="Live trading · XAUUSD">
          <div
            className={cn("grid gap-2 sm:grid-cols-2", focus === "live" && "ring-1 ring-[var(--border-strong)]")}
          >
            <MetricCard label="Session" value={str(live.session, "—")} />
            <MetricCard label="Regime" value={str(live.market_regime, "—")} />
            <MetricCard label="MTF" value={str(live.mtf_score, "—")} />
            <MetricCard label="Quality" value={str(live.quality, "—")} />
            <MetricCard label="Confluence" value={str(live.confluence, "—")} />
            <MetricCard label="Decision" value={str(live.execution_decision, "—")} />
            <MetricCard label="Risk" value={str(live.risk_status, "—")} />
            <MetricCard label="Safety" value={str(live.safety_status, "—")} />
          </div>
          <p className="mt-2 font-mono text-[11px] text-[var(--fg-subtle)]">
            Last eval · {str(live.last_evaluation, "—")}
          </p>
        </OpsPanel>

        <OpsPanel title="Portfolio">
          <div
            className={cn("grid gap-2 sm:grid-cols-2", focus === "portfolio" && "ring-1 ring-[var(--border-strong)]")}
          >
            <MetricCard label="Balance" value={fmt(portfolio.balance)} />
            <MetricCard label="Equity" value={fmt(portfolio.equity)} />
            <MetricCard label="Floating" value={fmt(portfolio.floating_pnl)} />
            <MetricCard label="Closed" value={fmt(portfolio.closed_pnl)} />
            <MetricCard label="Drawdown %" value={fmt(portfolio.drawdown)} />
            <MetricCard label="Health" value={str(portfolio.health_score, "—")} />
          </div>
        </OpsPanel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <OpsPanel title="Research">
          <div
            className={cn(focus === "research" && "ring-1 ring-[var(--border-strong)]")}
          >
            <div className="grid gap-2 sm:grid-cols-2">
              <MetricCard
                label="Running"
                value={String(num(research.running_experiments, 0))}
              />
              <MetricCard
                label="Completed"
                value={String(num(research.completed_experiments, 0))}
              />
            </div>
            <ul className="mt-3 space-y-1 text-[12px]">
              {board.map((r) => (
                <li key={str(r.uuid)} className="flex justify-between gap-2">
                  <span>
                    #{num(r.rank, 0)} {str(r.name)}
                  </span>
                  <span className="font-mono text-[var(--fg-muted)]">
                    {str(r.composite_score, "—")}
                  </span>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
              Promotion queue · {asList(research.promotion_queue).length} (governance
              only)
            </p>
          </div>
        </OpsPanel>

        <OpsPanel title="Data Warehouse">
          <div className="grid gap-2 sm:grid-cols-2">
            <MetricCard label="Events stored" value={str(warehouse.events_stored, "—")} />
            <MetricCard label="Integrity" value={str(warehouse.integrity_score, "—")} />
            <MetricCard label="Latency (s)" value={str(warehouse.latency, "—")} />
            <MetricCard label="Missing" value={str(warehouse.missing_events, "—")} />
            <MetricCard label="Duplicates" value={str(warehouse.duplicate_events, "—")} />
            <MetricCard label="Storage" value={str(warehouse.storage_health, "—")} />
          </div>
        </OpsPanel>
      </div>

      <OpsPanel title="Analytics desks">
        <div className="flex flex-wrap gap-2">
          {desks.map((d) => (
            <Button key={str(d.id)} asChild size="sm" variant="outline">
              <Link href={str(d.href, "/")}>{str(d.label)}</Link>
            </Button>
          ))}
        </div>
      </OpsPanel>

      <div className="grid gap-4 lg:grid-cols-2">
        <OpsPanel title="Active alerts">
          <div className={cn(focus === "alerts" && "ring-1 ring-[var(--border-strong)]")}>
            {alerts.length === 0 ? (
              <p className="text-[12px] text-[var(--fg-subtle)]">No active alerts.</p>
            ) : (
              <ul className="space-y-2">
                {alerts.map((a) => (
                  <li
                    key={str(a.id)}
                    className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
                  >
                    <Badge tone={statusTone(str(a.severity))}>{str(a.severity)}</Badge>
                    <Badge tone="neutral">{str(a.category)}</Badge>
                    <span>{str(a.message)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </OpsPanel>

        <OpsPanel title="Operational timeline">
          <ul className="max-h-64 space-y-2 overflow-auto text-[12px]">
            {events.map((e, i) => (
              <li key={`${str(e.timestamp)}-${i}`} className="border-b border-[var(--border)]/40 pb-2">
                <p className="font-mono text-[10px] text-[var(--fg-subtle)]">
                  {str(e.timestamp, "").slice(0, 19)}
                </p>
                <p className="text-[var(--fg)]">{str(e.kind)}</p>
                <p className="text-[var(--fg-muted)]">{str(e.detail, "")}</p>
              </li>
            ))}
          </ul>
        </OpsPanel>
      </div>

      <OpsPanel title="Architecture view">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {archNodes.map((n) => (
            <Link
              key={str(n.id)}
              href={str(n.href, "/")}
              className="border border-[var(--border)] px-3 py-3 hover:bg-[var(--surface-2)]/40"
            >
              <p className="text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                {str(n.group)}
              </p>
              <p className="mt-1 text-[13px] text-[var(--fg)]">{str(n.label)}</p>
            </Link>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}
