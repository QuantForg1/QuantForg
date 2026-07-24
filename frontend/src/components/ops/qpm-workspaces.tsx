"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qpmApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-portfolio-manager", label: "Dashboard" },
  { href: "/quantforg-portfolio-manager/allocation", label: "Allocation" },
  { href: "/quantforg-portfolio-manager/ranking", label: "Ranking" },
  {
    href: "/quantforg-portfolio-manager/diversification",
    label: "Diversification",
  },
  { href: "/quantforg-portfolio-manager/reports", label: "Reports" },
] as const;

export function QpmNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-portfolio-manager"
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

function IsolationBadges() {
  return (
    <div className="flex flex-wrap gap-2">
      <Badge tone="neutral">PORTFOLIO MANAGER</Badge>
      <Badge tone="success">READ-ONLY</Badge>
      <Badge tone="warning">HUMAN APPROVAL REQUIRED</Badge>
      <Badge tone="neutral">NEVER AUTO-REBALANCE</Badge>
    </div>
  );
}

export function QpmDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["qpm", "dashboard"],
    queryFn: () => qpmApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "QPM unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const metrics = asRecord(root.metrics);
  const health = asRecord(root.portfolio_health);
  const readiness = asRecord(root.portfolio_readiness);
  const recommendations = asList(root.recommendations).map(asRecord);

  return (
    <div className="space-y-4">
      <QpmNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Advisory portfolio orchestration across certified strategies. Never
        allocates capital or rebalances automatically.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Portfolio health"
          value={str(health.overall_portfolio_health, "—")}
        />
        <MetricCard
          label="Confidence"
          value={str(metrics.portfolio_confidence_score, "—")}
        />
        <MetricCard
          label="Sharpe"
          value={str(metrics.portfolio_sharpe, "—")}
        />
        <MetricCard
          label="Drawdown"
          value={str(metrics.portfolio_drawdown, "—")}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Sortino"
          value={str(metrics.portfolio_sortino, "—")}
        />
        <MetricCard
          label="Diversification"
          value={str(metrics.diversification_score, "—")}
        />
        <MetricCard
          label="Corr risk"
          value={str(metrics.correlation_risk, "—")}
        />
        <MetricCard
          label="Capital util"
          value={str(metrics.capital_utilization, "—")}
        />
      </div>
      <OpsPanel title="Readiness">
        <div className="flex flex-wrap gap-2 text-[12px]">
          <Badge tone={readiness.ready ? "success" : "warning"}>
            {readiness.ready ? "ready" : "not ready"}
          </Badge>
          <span className="text-[var(--fg-muted)]">
            platform {str(readiness.platform_certification_level)} · certified
            strategies {str(readiness.certified_or_staging_strategies)}
          </span>
        </div>
      </OpsPanel>
      <OpsPanel title="Recommendations (human approval required)">
        <ul className="space-y-2">
          {recommendations.slice(0, 10).map((r, i) => (
            <li
              key={`${str(r.strategy_id)}-${i}`}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="warning">{str(r.kind)}</Badge>
              <span className="font-mono text-[11px]">
                {str(r.strategy_id)}
              </span>
              <span className="text-[var(--fg-muted)]">{str(r.detail)}</span>
            </li>
          ))}
          {!recommendations.length ? (
            <li className="text-[12px] text-[var(--fg-muted)]">
              No recommendations in current snapshot.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function QpmAllocationWorkspace() {
  const q = useQuery({
    queryKey: ["qpm", "allocation"],
    queryFn: () => qpmApi.allocation(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Allocation unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const allocation = asRecord(root.capital_allocation);
  const rows = asList(allocation.allocations).map(asRecord);
  const exposure = asRecord(root.portfolio_exposure);

  return (
    <div className="space-y-4">
      <QpmNav />
      <IsolationBadges />
      <MetricCard
        label="Total weight %"
        value={str(allocation.total_weight_pct, "—")}
      />
      <OpsPanel title="Allocation explorer (advisory)">
        <ul className="space-y-2 text-[12px]">
          {rows.map((r) => (
            <li
              key={str(r.strategy_id)}
              className="flex flex-wrap gap-2 border border-[var(--border)]/60 px-3 py-2"
            >
              <Badge tone="neutral">#{str(r.rank)}</Badge>
              <span className="font-mono text-[11px]">
                {str(r.strategy_id)}
              </span>
              <span>{str(r.strategy_name)}</span>
              <span className="text-[var(--fg-muted)]">
                {str(r.recommended_weight_pct)}%
              </span>
            </li>
          ))}
        </ul>
      </OpsPanel>
      <OpsPanel title="Exposure by lifecycle">
        <pre className="max-h-48 overflow-auto text-[11px] text-[var(--fg-muted)]">
          {JSON.stringify(exposure.by_lifecycle_pct, null, 2)}
        </pre>
      </OpsPanel>
    </div>
  );
}

export function QpmRankingWorkspace() {
  const q = useQuery({
    queryKey: ["qpm", "ranking"],
    queryFn: () => qpmApi.ranking(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Ranking unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const ranked = asList(asRecord(q.data).strategy_ranking).map(asRecord);

  return (
    <div className="space-y-4">
      <QpmNav />
      <IsolationBadges />
      <OpsPanel title="Strategy ranking">
        <ul className="space-y-2 text-[12px]">
          {ranked.map((r) => (
            <li
              key={str(r.strategy_id)}
              className="flex flex-wrap gap-2 border border-[var(--border)]/60 px-3 py-2"
            >
              <Badge tone="neutral">#{str(r.rank)}</Badge>
              <span>{str(r.strategy_name)}</span>
              <span className="font-mono text-[11px]">
                {str(r.strategy_id)}
              </span>
              <span className="text-[var(--fg-muted)]">
                composite {str(r.composite_rank_score)}
              </span>
              <Badge tone="neutral">{str(r.certification_status)}</Badge>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function QpmDiversificationWorkspace() {
  const q = useQuery({
    queryKey: ["qpm", "diversification"],
    queryFn: () => qpmApi.diversification(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Diversification unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const matrix = asRecord(asRecord(q.data).diversification_matrix);
  const diversification = asRecord(matrix.diversification);
  const correlation = asRecord(matrix.correlation);

  return (
    <div className="space-y-4">
      <QpmNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard
          label="Diversification"
          value={str(diversification.diversification_score, "—")}
        />
        <MetricCard
          label="Avg pairwise corr"
          value={str(correlation.average_pairwise_correlation, "—")}
        />
        <MetricCard
          label="Corr risk"
          value={str(correlation.correlation_risk_score, "—")}
        />
      </div>
      <OpsPanel title="Correlation matrix labels">
        <p className="mb-2 text-[11px] text-[var(--fg-subtle)]">
          {str(correlation.note)}
        </p>
        <ul className="flex flex-wrap gap-2 text-[11px]">
          {asList(correlation.labels).map((l, i) => (
            <Badge key={i} tone="neutral">
              {str(l)}
            </Badge>
          ))}
        </ul>
        <pre className="mt-3 max-h-64 overflow-auto text-[10px] text-[var(--fg-muted)]">
          {JSON.stringify(correlation.matrix, null, 2)}
        </pre>
      </OpsPanel>
    </div>
  );
}

export function QpmReportsWorkspace() {
  const q = useQuery({
    queryKey: ["qpm", "reports"],
    queryFn: () => qpmApi.reports(20),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Reports unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const reports = asList(asRecord(q.data).reports).map(asRecord);

  return (
    <div className="space-y-4">
      <QpmNav />
      <IsolationBadges />
      <OpsPanel title="Portfolio reports">
        <ul className="space-y-2 text-[12px]">
          {reports.map((r) => (
            <li
              key={str(r.report_id)}
              className="border border-[var(--border)]/60 px-3 py-2"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">{str(r.kind)}</Badge>
                <span className="font-mono text-[11px]">
                  {str(r.report_id)}
                </span>
              </div>
              <p className="mt-1 text-[var(--fg-muted)]">{str(r.title)}</p>
            </li>
          ))}
          {!reports.length ? (
            <li className="text-[var(--fg-muted)]">No reports yet.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}
