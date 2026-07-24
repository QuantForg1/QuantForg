"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { cvfApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/continuous-validation", label: "Dashboard" },
  { href: "/continuous-validation/drift", label: "Drift" },
  { href: "/continuous-validation/replay-vs-live", label: "Replay vs Live" },
  { href: "/continuous-validation/confidence", label: "Confidence" },
  { href: "/continuous-validation/evidence", label: "Evidence" },
  { href: "/continuous-validation/reports", label: "Reports" },
] as const;

export function CvfNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/continuous-validation"
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

function useCvfDashboard() {
  return useQuery({
    queryKey: ["cvf", "dashboard"],
    queryFn: () => cvfApi.dashboard(),
    refetchInterval: 60_000,
  });
}

export function CvfDashboardWorkspace() {
  const q = useCvfDashboard();
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "CVF unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const confidence = asRecord(root.confidence);
  const alerts = asList(root.alerts).map(asRecord);
  const drift = asRecord(root.drift);

  return (
    <div className="space-y-4">
      <CvfNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">CONTINUOUS VALIDATION</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">EVIDENCE ONLY</Badge>
        <Badge tone="warning">HUMANS DECIDE</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Validates live trading against research baselines. Never modifies
        production, thresholds, or approves promotions.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Confidence" value={str(confidence.confidence, "—")} />
        <MetricCard
          label="Evidence score"
          value={str(confidence.evidence_score, "—")}
        />
        <MetricCard label="Drift count" value={str(drift.drift_count, "—")} />
        <MetricCard label="Alerts" value={String(alerts.length)} />
      </div>

      <OpsPanel title="Read-only validation alerts">
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
              No validation alerts in current snapshot.
            </li>
          ) : null}
        </ul>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button asChild size="sm" variant="outline">
            <Link href="/continuous-validation/drift">Drift explorer</Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/continuous-validation/evidence">Evidence</Link>
          </Button>
        </div>
      </OpsPanel>
    </div>
  );
}

export function CvfDriftWorkspace() {
  const q = useQuery({
    queryKey: ["cvf", "drift"],
    queryFn: () => cvfApi.drift(),
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
  const drift = asRecord(asRecord(q.data).drift);
  const rows = asList(drift.drifts).map(asRecord);

  return (
    <div className="space-y-4">
      <CvfNav />
      <OpsPanel title="Strategy drift explorer">
        <ul className="space-y-2">
          {rows.map((d, i) => (
            <li
              key={`${str(d.kind)}-${i}`}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge
                tone={
                  str(d.severity) === "critical"
                    ? "danger"
                    : str(d.severity) === "info"
                      ? "neutral"
                      : "warning"
                }
              >
                {str(d.severity)}
              </Badge>
              <span className="font-medium">{str(d.kind)}</span>
              <span className="text-[var(--fg-muted)]">
                Δ {str(d.delta_pct)}% · live:{str(d.live, "—")} replay:
                {str(d.replay, "—")}
              </span>
            </li>
          ))}
          {!rows.length ? (
            <li className="text-[var(--fg-muted)]">No drift signals.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function CvfReplayVsLiveWorkspace() {
  const q = useQuery({
    queryKey: ["cvf", "replay-vs-live"],
    queryFn: () => cvfApi.replayVsLive(),
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
  const pack = asRecord(asRecord(q.data).replay_vs_live);
  const rows = asList(pack.comparison).map(asRecord);

  return (
    <div className="space-y-4">
      <CvfNav />
      <OpsPanel title="Replay vs live">
        <ul className="space-y-2">
          {rows.map((r) => (
            <li
              key={str(r.metric)}
              className="grid grid-cols-2 gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px] sm:grid-cols-4"
            >
              <span className="font-medium">{str(r.metric)}</span>
              <span>replay:{str(r.replay, "—")}</span>
              <span>live:{str(r.live, "—")}</span>
              <span>Δ%{str(r.delta_pct, "—")}</span>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function CvfConfidenceWorkspace() {
  const q = useQuery({
    queryKey: ["cvf", "confidence"],
    queryFn: () => cvfApi.confidence(),
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
  const c = asRecord(asRecord(q.data).confidence);

  return (
    <div className="space-y-4">
      <CvfNav />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="Confidence" value={str(c.confidence, "—")} />
        <MetricCard label="Sample size" value={str(c.sample_size, "—")} />
        <MetricCard label="Variance" value={str(c.variance, "—")} />
        <MetricCard label="Stability" value={str(c.stability_score, "—")} />
        <MetricCard label="Reliability" value={str(c.reliability_score, "—")} />
        <MetricCard label="Evidence" value={str(c.evidence_score, "—")} />
      </div>
    </div>
  );
}

export function CvfEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["cvf", "evidence"],
    queryFn: () => cvfApi.evidence(),
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
  const chains = asList(asRecord(q.data).evidence_chains).map(asRecord);

  return (
    <div className="space-y-4">
      <CvfNav />
      <OpsPanel title="Evidence chains">
        <ul className="space-y-3">
          {chains.map((chain, i) => (
            <li
              key={i}
              className="border border-[var(--border)] px-3 py-3 text-[12px]"
            >
              <Badge tone="neutral">
                {str(asRecord(chain.alert).kind, "baseline")}
              </Badge>
              <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-[11px] text-[var(--fg-muted)]">
                {JSON.stringify(
                  {
                    historical_baseline: chain.historical_baseline,
                    current_observations: chain.current_observations,
                    supporting_statistics: chain.supporting_statistics,
                    knowledge_graph_links: chain.knowledge_graph_links,
                  },
                  null,
                  2,
                )}
              </pre>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function CvfReportsWorkspace() {
  const q = useQuery({
    queryKey: ["cvf", "reports"],
    queryFn: () => cvfApi.reports(20),
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
      <CvfNav />
      <OpsPanel title="Executive validation reports">
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
              <p className="mt-1 text-[var(--fg-muted)]">{str(r.summary)}</p>
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
