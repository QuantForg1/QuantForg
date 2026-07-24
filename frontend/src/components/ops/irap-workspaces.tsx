"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { irapApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/institutional-risk-analytics", label: "Dashboard" },
  { href: "/institutional-risk-analytics/exposure", label: "Exposure" },
  { href: "/institutional-risk-analytics/drawdown", label: "Drawdown" },
  { href: "/institutional-risk-analytics/correlation", label: "Correlation" },
  { href: "/institutional-risk-analytics/stress", label: "Stress Risk" },
  { href: "/institutional-risk-analytics/reports", label: "Reports" },
] as const;

export function IrapNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/institutional-risk-analytics"
            ? pathname === link.href
            : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "px-3 py-1.5 text-[12px] uppercase tracking-[0.1em]",
              active
                ? "border border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--fg)]"
                : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function IrapDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["irap", "dashboard"],
    queryFn: () => irapApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "IRAP unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const metrics = asRecord(root.metrics);
  const alerts = asList(root.alerts).map(asRecord);

  return (
    <div className="space-y-4">
      <IrapNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">INSTITUTIONAL RISK ANALYTICS</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">NEVER MODIFIES RISK</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Portfolio and strategy risk intelligence from historical, live and
        simulated evidence. Never modifies production or risk parameters.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Sharpe" value={str(metrics.sharpe_ratio, "—")} />
        <MetricCard label="Sortino" value={str(metrics.sortino_ratio, "—")} />
        <MetricCard label="Calmar" value={str(metrics.calmar_ratio, "—")} />
        <MetricCard
          label="Max DD%"
          value={str(metrics.maximum_drawdown, "—")}
        />
        <MetricCard label="VaR" value={str(metrics.value_at_risk, "—")} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="CVaR" value={str(metrics.conditional_var, "—")} />
        <MetricCard
          label="Risk of ruin"
          value={str(metrics.risk_of_ruin, "—")}
        />
        <MetricCard
          label="Recovery"
          value={str(metrics.recovery_factor, "—")}
        />
        <MetricCard label="PF" value={str(metrics.profit_factor, "—")} />
        <MetricCard label="Expectancy" value={str(metrics.expectancy, "—")} />
      </div>

      <OpsPanel title="Read-only risk alerts">
        <ul className="space-y-2">
          {alerts.map((a, i) => (
            <li
              key={`${str(a.kind)}-${i}`}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge
                tone={str(a.severity) === "critical" ? "danger" : "warning"}
              >
                {str(a.kind)}
              </Badge>
              <span>{str(a.detail)}</span>
            </li>
          ))}
          {!alerts.length ? (
            <li className="text-[12px] text-[var(--fg-muted)]">
              No risk alerts in current snapshot.
            </li>
          ) : null}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/institutional-risk-analytics/exposure">Exposure</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/institutional-risk-analytics/stress">Stress risk</Link>
          </Button>
        </div>
      </OpsPanel>
    </div>
  );
}

export function IrapExposureWorkspace() {
  const q = useQuery({
    queryKey: ["irap", "exposure"],
    queryFn: () => irapApi.exposure(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const exposure = asRecord(root.exposure);
  const concentration = asRecord(root.concentration);
  const sessions = asRecord(exposure.by_session);
  const symbols = asRecord(exposure.by_symbol);

  return (
    <div className="space-y-4">
      <IrapNav />
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard
          label="Symbol concentration %"
          value={str(concentration.symbol_concentration_pct, "—")}
        />
        <MetricCard label="HHI" value={str(concentration.symbol_hhi, "—")} />
        <MetricCard
          label="Avg exposure %"
          value={str(exposure.avg_exposure_pct, "—")}
        />
      </div>
      <OpsPanel title="By session">
        <ul className="space-y-2">
          {Object.entries(sessions).map(([k, v]) => {
            const row = asRecord(v);
            return (
              <li
                key={k}
                className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
              >
                {k} · trades:{str(row.trade_count)} wr:{str(row.win_rate, "—")}{" "}
                pnl:{str(row.pnl, "—")}
              </li>
            );
          })}
        </ul>
      </OpsPanel>
      <OpsPanel title="By symbol">
        <div className="flex flex-wrap gap-2">
          {Object.entries(symbols).map(([k, v]) => (
            <Badge key={k} tone="neutral">
              {k}:{String(v)}
            </Badge>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function IrapDrawdownWorkspace() {
  const q = useQuery({
    queryKey: ["irap", "drawdown"],
    queryFn: () => irapApi.drawdown(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const d = asRecord(asRecord(q.data).drawdown);

  return (
    <div className="space-y-4">
      <IrapNav />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Max DD%"
          value={str(d.maximum_drawdown_pct, "—")}
        />
        <MetricCard
          label="Current DD%"
          value={str(d.current_drawdown_pct, "—")}
        />
        <MetricCard label="Ulcer index" value={str(d.ulcer_index, "—")} />
        <MetricCard label="Trend" value={str(d.drawdown_trend, "—")} />
      </div>
    </div>
  );
}

export function IrapCorrelationWorkspace() {
  const q = useQuery({
    queryKey: ["irap", "correlation"],
    queryFn: () => irapApi.correlation(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const c = asRecord(asRecord(q.data).correlation);
  const matrix = asList(c.session_matrix).map(asRecord);

  return (
    <div className="space-y-4">
      <IrapNav />
      <OpsPanel title="Session correlation matrix">
        <pre className="max-h-[480px] overflow-auto whitespace-pre-wrap text-[11px] text-[var(--fg-muted)]">
          {JSON.stringify(matrix, null, 2)}
        </pre>
      </OpsPanel>
    </div>
  );
}

export function IrapStressWorkspace() {
  const q = useQuery({
    queryKey: ["irap", "stress"],
    queryFn: () => irapApi.stress(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const stress = asRecord(root.stress_loss);
  const tail = asRecord(root.tail_risk);
  const scenarios = asList(stress.stress_scenarios).map(asRecord);

  return (
    <div className="space-y-4">
      <IrapNav />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Avg stress DD"
          value={str(stress.average_stress_drawdown, "—")}
        />
        <MetricCard
          label="Max stress DD"
          value={str(stress.max_stress_drawdown, "—")}
        />
        <MetricCard label="VaR" value={str(tail.value_at_risk, "—")} />
        <MetricCard label="CVaR" value={str(tail.conditional_var, "—")} />
      </div>
      <OpsPanel title="Stress scenarios">
        <ul className="space-y-2">
          {scenarios.map((s, i) => (
            <li
              key={`${str(s.simulation_id)}-${i}`}
              className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="warning">{str(s.scenario)}</Badge> DD:
              {str(s.drawdown, "—")} PF:{str(s.profit_factor, "—")}
            </li>
          ))}
          {!scenarios.length ? (
            <li className="text-[var(--fg-muted)]">
              No ISE stress simulations in cache yet.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IrapReportsWorkspace() {
  const q = useQuery({
    queryKey: ["irap", "reports"],
    queryFn: () => irapApi.reports(20),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const rows = asList(asRecord(q.data).reports).map(asRecord);

  return (
    <div className="space-y-4">
      <IrapNav />
      <OpsPanel title="Risk reports">
        <ul className="space-y-2">
          {rows.map((r) => (
            <li
              key={str(r.report_id)}
              className="border border-[var(--border)] px-3 py-2 text-[12px]"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">{str(r.period || r.kind)}</Badge>
                <span>{str(r.title)}</span>
              </div>
              <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap text-[11px] text-[var(--fg-muted)]">
                {JSON.stringify(r.metrics || r.stress || r, null, 2)}
              </pre>
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">No reports yet.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}
