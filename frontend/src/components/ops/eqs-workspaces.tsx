"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { eqsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/execution-quality-suite", label: "Dashboard" },
  { href: "/execution-quality-suite/latency", label: "Latency" },
  { href: "/execution-quality-suite/slippage", label: "Slippage" },
  { href: "/execution-quality-suite/timeline", label: "Timeline" },
  { href: "/execution-quality-suite/broker", label: "Broker Health" },
  { href: "/execution-quality-suite/score", label: "Score" },
  { href: "/execution-quality-suite/reports", label: "Reports" },
] as const;

export function EqsNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/execution-quality-suite"
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

function useEqsDashboard() {
  return useQuery({
    queryKey: ["eqs", "dashboard"],
    queryFn: () => eqsApi.dashboard(),
    refetchInterval: 60_000,
  });
}

function LatencyBlock({
  title,
  stats,
}: {
  title: string;
  stats: Record<string, unknown>;
}) {
  return (
    <div className="border border-[var(--border)]/60 px-3 py-2 text-[12px]">
      <p className="mb-1 font-medium">{title}</p>
      <div className="grid grid-cols-2 gap-1 text-[var(--fg-muted)] sm:grid-cols-5">
        <span>avg:{str(stats.average, "—")}</span>
        <span>med:{str(stats.median, "—")}</span>
        <span>p95:{str(stats.p95, "—")}</span>
        <span>max:{str(stats.maximum, "—")}</span>
        <span>min:{str(stats.minimum, "—")}</span>
      </div>
    </div>
  );
}

export function EqsDashboardWorkspace() {
  const q = useEqsDashboard();
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "EQS unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const score = asRecord(root.execution_score);
  const alerts = asList(root.alerts).map(asRecord);
  const fillActual = asRecord(root.fill_quality);

  return (
    <div className="space-y-4">
      <EqsNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">EXECUTION QUALITY SUITE</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">NEVER EXECUTES</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Execution intelligence from signal to broker fill. Never modifies
        production, OMS, gateway, risk, or thresholds.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Overall score"
          value={str(score.overall_execution_score, "—")}
        />
        <MetricCard label="Latency score" value={str(score.latency, "—")} />
        <MetricCard label="Fill quality" value={str(score.fill_quality, "—")} />
        <MetricCard
          label="Success rate"
          value={str(fillActual.execution_success_rate, "—")}
        />
      </div>

      <OpsPanel title="Read-only alerts">
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
              No execution alerts in current snapshot.
            </li>
          ) : null}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/execution-quality-suite/latency">Latency explorer</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/execution-quality-suite/timeline">Timelines</Link>
          </Button>
        </div>
      </OpsPanel>
    </div>
  );
}

export function EqsLatencyWorkspace() {
  const q = useQuery({
    queryKey: ["eqs", "latency"],
    queryFn: () => eqsApi.latency(),
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
  const lat = asRecord(asRecord(q.data).latency);

  return (
    <div className="space-y-4">
      <EqsNav />
      <OpsPanel title="Latency analytics (ms)">
        <div className="space-y-2">
          <LatencyBlock title="Strategy" stats={asRecord(lat.strategy_latency)} />
          <LatencyBlock title="OMS" stats={asRecord(lat.oms_latency)} />
          <LatencyBlock title="Gateway" stats={asRecord(lat.gateway_latency)} />
          <LatencyBlock title="Broker" stats={asRecord(lat.broker_latency)} />
          <LatencyBlock title="Fill" stats={asRecord(lat.fill_latency)} />
          <LatencyBlock
            title="Total execution"
            stats={asRecord(lat.total_execution_latency)}
          />
        </div>
      </OpsPanel>
    </div>
  );
}

export function EqsSlippageWorkspace() {
  const q = useQuery({
    queryKey: ["eqs", "slippage"],
    queryFn: () => eqsApi.slippage(),
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
  const slip = asRecord(asRecord(q.data).slippage);
  const rows = asList(slip.rows).map(asRecord);

  return (
    <div className="space-y-4">
      <EqsNav />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Average" value={str(slip.average_slippage, "—")} />
        <MetricCard label="Worst" value={str(slip.worst_slippage, "—")} />
        <MetricCard label="Best" value={str(slip.best_slippage, "—")} />
        <MetricCard label="Sample" value={str(slip.sample_size, "—")} />
      </div>
      <OpsPanel title="Slippage rows">
        <ul className="space-y-2">
          {rows.slice(0, 30).map((r, i) => (
            <li
              key={`${str(r.order_id)}-${i}`}
              className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              {str(r.order_id)} · expected:{str(r.expected_entry, "—")} actual:
              {str(r.actual_entry, "—")} slip:{str(r.slippage, "—")}
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">No slippage samples.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function EqsTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["eqs", "timelines"],
    queryFn: () => eqsApi.timelines(40),
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
  const rows = asList(asRecord(q.data).timelines).map(asRecord);

  return (
    <div className="space-y-4">
      <EqsNav />
      <OpsPanel title="Execution timelines">
        <ul className="space-y-3">
          {rows.map((t) => (
            <li
              key={str(t.order_id)}
              className="border border-[var(--border)] px-3 py-3 text-[12px]"
            >
              <div className="mb-2 flex flex-wrap gap-2">
                <Badge tone="neutral">{str(t.symbol, "—")}</Badge>
                <Badge tone="warning">{str(t.result, "—")}</Badge>
                <span className="text-[var(--fg-muted)]">{str(t.order_id)}</span>
              </div>
              <ol className="space-y-1 border-l border-[var(--border)] pl-3">
                {asList(t.timeline)
                  .map(asRecord)
                  .map((s) => (
                    <li key={str(s.stage)}>
                      {str(s.stage)} → {str(s.timestamp, "—")}
                    </li>
                  ))}
              </ol>
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">No timelines in snapshot.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function EqsBrokerWorkspace() {
  const q = useQuery({
    queryKey: ["eqs", "broker"],
    queryFn: () => eqsApi.brokerHealth(),
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
  const b = asRecord(asRecord(q.data).broker_health);

  return (
    <div className="space-y-4">
      <EqsNav />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="Uptime" value={str(b.connection_uptime, "—")} />
        <MetricCard
          label="Response latency"
          value={str(b.response_latency, "—")}
        />
        <MetricCard label="Failures" value={str(b.execution_failures, "—")} />
        <MetricCard label="Reconnects" value={str(b.reconnect_count, "—")} />
        <MetricCard label="Health score" value={str(b.health_score, "—")} />
      </div>
    </div>
  );
}

export function EqsScoreWorkspace() {
  const q = useQuery({
    queryKey: ["eqs", "score"],
    queryFn: () => eqsApi.score(),
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
  const s = asRecord(asRecord(q.data).execution_score);

  return (
    <div className="space-y-4">
      <EqsNav />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard
          label="Overall"
          value={str(s.overall_execution_score, "—")}
        />
        <MetricCard label="Latency" value={str(s.latency, "—")} />
        <MetricCard label="Slippage" value={str(s.slippage, "—")} />
        <MetricCard label="Fill quality" value={str(s.fill_quality, "—")} />
        <MetricCard label="Consistency" value={str(s.consistency, "—")} />
        <MetricCard label="Reliability" value={str(s.reliability, "—")} />
      </div>
    </div>
  );
}

export function EqsReportsWorkspace() {
  const q = useQuery({
    queryKey: ["eqs", "reports"],
    queryFn: () => eqsApi.reports(20),
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
      <EqsNav />
      <OpsPanel title="Execution reports">
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
                {JSON.stringify(r.execution_score || r.latency || r, null, 2)}
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
