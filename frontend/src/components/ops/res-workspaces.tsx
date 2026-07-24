"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { resApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/reliability-engineering-suite", label: "Dashboard" },
  { href: "/reliability-engineering-suite/health", label: "Health" },
  { href: "/reliability-engineering-suite/recovery", label: "Recovery" },
  { href: "/reliability-engineering-suite/failures", label: "Failures" },
  { href: "/reliability-engineering-suite/reports", label: "Reports" },
] as const;

export function ResNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/reliability-engineering-suite"
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

function useResDashboard() {
  return useQuery({
    queryKey: ["res", "dashboard"],
    queryFn: () => resApi.dashboard(),
    refetchInterval: 60_000,
  });
}

export function ResDashboardWorkspace() {
  const q = useResDashboard();
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "RES unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const health = asRecord(root.platform_health);
  const score = asRecord(root.reliability_score);

  return (
    <div className="space-y-4">
      <ResNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">RELIABILITY ENGINEERING SUITE</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">NEVER EXECUTES</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Platform health, availability, recovery and failure analytics. Never
        modifies production or triggers automation.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          label="Overall health"
          value={str(health.overall_health, "—")}
        />
        <MetricCard
          label="Availability"
          value={str(health.availability, "—")}
        />
        <MetricCard
          label="Reliability score"
          value={str(score.overall_reliability_score, "—")}
        />
        <MetricCard
          label="Active incidents"
          value={str(health.active_incidents, "—")}
        />
        <MetricCard
          label="Open warnings"
          value={str(health.open_warnings, "—")}
        />
      </div>

      <OpsPanel title="Score breakdown">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          <MetricCard label="Availability" value={str(score.availability, "—")} />
          <MetricCard label="Recovery" value={str(score.recovery, "—")} />
          <MetricCard label="Consistency" value={str(score.consistency, "—")} />
          <MetricCard label="Failure rate" value={str(score.failure_rate, "—")} />
          <MetricCard
            label="Latency stability"
            value={str(score.latency_stability, "—")}
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/reliability-engineering-suite/health">Health explorer</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/reliability-engineering-suite/failures">Failures</Link>
          </Button>
        </div>
      </OpsPanel>
    </div>
  );
}

export function ResHealthWorkspace() {
  const q = useQuery({
    queryKey: ["res", "services"],
    queryFn: () => resApi.services(),
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
  const rows = asList(asRecord(q.data).services).map(asRecord);

  return (
    <div className="space-y-4">
      <ResNav />
      <OpsPanel title="Service reliability">
        <ul className="space-y-2">
          {rows.map((s) => (
            <li
              key={str(s.service)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge
                tone={
                  str(s.status) === "critical"
                    ? "danger"
                    : str(s.status) === "degraded"
                      ? "warning"
                      : "success"
                }
              >
                {str(s.status)}
              </Badge>
              <span className="font-medium">{str(s.service)}</span>
              <span className="text-[var(--fg-muted)]">
                health:{str(s.health)} · latency:{str(s.latency, "—")} ·
                restarts:{str(s.restart_count)} · failures:
                {str(s.failure_count)}
              </span>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function ResRecoveryWorkspace() {
  const q = useQuery({
    queryKey: ["res", "recovery"],
    queryFn: () => resApi.recovery(),
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
  const r = asRecord(asRecord(q.data).recovery);

  return (
    <div className="space-y-4">
      <ResNav />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard label="MTTD (sec)" value={str(r.mttd_sec, "—")} />
        <MetricCard label="MTTR (sec)" value={str(r.mttr_sec, "—")} />
        <MetricCard
          label="Recovery success %"
          value={str(r.recovery_success_rate, "—")}
        />
        <MetricCard
          label="Automatic recoveries"
          value={str(r.automatic_recovery_events, "—")}
        />
        <MetricCard
          label="Manual recoveries"
          value={str(r.manual_recovery_events, "—")}
        />
      </div>
    </div>
  );
}

export function ResFailuresWorkspace() {
  const q = useQuery({
    queryKey: ["res", "failures"],
    queryFn: () => resApi.failures(),
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
  const f = asRecord(asRecord(q.data).failures);
  const byClass = asRecord(f.by_class);
  const samples = asList(f.samples).map(asRecord);

  return (
    <div className="space-y-4">
      <ResNav />
      <OpsPanel title="Failure classification">
        <div className="mb-3 flex flex-wrap gap-2">
          {Object.entries(byClass).map(([k, v]) => (
            <Badge key={k} tone={Number(v) > 0 ? "warning" : "neutral"}>
              {k}:{String(v)}
            </Badge>
          ))}
        </div>
        <p className="mb-2 text-[12px] text-[var(--fg-muted)]">
          Total failures: {str(f.total_failures, "0")}
        </p>
        <ul className="space-y-2">
          {samples.slice(0, 25).map((s, i) => (
            <li
              key={`${str(s.class)}-${i}`}
              className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="warning">{str(s.class)}</Badge>{" "}
              <span className="text-[var(--fg-muted)]">{str(s.domain)}</span>
              <p className="mt-1">{str(s.summary)}</p>
            </li>
          ))}
          {!samples.length ? (
            <li className="text-[var(--fg-muted)]">No classified failures.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function ResReportsWorkspace() {
  const q = useQuery({
    queryKey: ["res", "reports"],
    queryFn: () => resApi.reports(20),
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
      <ResNav />
      <OpsPanel title="Reliability reports">
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
                {JSON.stringify(
                  r.reliability_score || r.platform_health || r,
                  null,
                  2,
                )}
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
