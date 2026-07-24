"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qcsApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-certification", label: "Dashboard" },
  { href: "/quantforg-certification/readiness", label: "Readiness" },
  { href: "/quantforg-certification/evidence", label: "Evidence" },
  { href: "/quantforg-certification/timeline", label: "Timeline" },
  { href: "/quantforg-certification/blockers", label: "Blockers" },
  { href: "/quantforg-certification/reports", label: "Reports" },
] as const;

export function QcsNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-certification"
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
      <Badge tone="neutral">CERTIFICATION SUITE</Badge>
      <Badge tone="success">READ-ONLY</Badge>
      <Badge tone="warning">HUMAN APPROVAL REQUIRED</Badge>
      <Badge tone="neutral">NEVER AUTO-APPROVE</Badge>
    </div>
  );
}

export function QcsDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["qcs", "dashboard"],
    queryFn: () => qcsApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "QCS unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const scores = asRecord(root.scores);
  const level = asRecord(root.level);
  const blockers = asList(root.blockers).map(asRecord);
  const checks = asList(root.checks).map(asRecord);

  return (
    <div className="space-y-4">
      <QcsNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Final institutional quality gate. Computes readiness from enterprise
        evidence. Never modifies production or approves releases automatically.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Level" value={str(level.level, "—")} />
        <MetricCard
          label="Overall readiness"
          value={str(scores.overall_institutional_readiness_score, "—")}
        />
        <MetricCard label="Blockers" value={String(blockers.length)} />
        <MetricCard label="Checks" value={String(checks.length)} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          label="Architecture"
          value={str(scores.architecture_score, "—")}
        />
        <MetricCard label="Quality" value={str(scores.quality_score, "—")} />
        <MetricCard label="Validation" value={str(scores.validation_score, "—")} />
        <MetricCard label="Risk" value={str(scores.risk_score, "—")} />
        <MetricCard
          label="Execution"
          value={str(scores.execution_score, "—")}
        />
      </div>
      <OpsPanel title="Top blockers">
        <ul className="space-y-2">
          {blockers.slice(0, 8).map((b, i) => (
            <li
              key={`${str(b.kind)}-${i}`}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge
                tone={
                  str(b.severity) === "Critical" ? "danger" : "warning"
                }
              >
                {str(b.severity)}
              </Badge>
              <span className="font-medium">{str(b.kind)}</span>
              <span className="text-[var(--fg-muted)]">{str(b.detail)}</span>
            </li>
          ))}
          {!blockers.length ? (
            <li className="text-[12px] text-[var(--fg-muted)]">
              No blockers in current assessment.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function QcsReadinessWorkspace() {
  const q = useQuery({
    queryKey: ["qcs", "readiness"],
    queryFn: () => qcsApi.readiness(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Readiness unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const center = asRecord(asRecord(q.data).readiness_center);
  const level = asRecord(center.level);
  const domains = asList(center.domains).map(asRecord);
  const scores = asRecord(center.scores);

  return (
    <div className="space-y-4">
      <QcsNav />
      <IsolationBadges />
      <MetricCard label="Certification level" value={str(level.level, "—")} />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {(
          [
            ["Research", "research_score"],
            ["Reliability", "reliability_score"],
            ["Security", "security_score"],
            ["Performance", "performance_score"],
            ["Documentation", "documentation_score"],
          ] as const
        ).map(([label, key]) => (
          <MetricCard key={key} label={label} value={str(scores[key], "—")} />
        ))}
      </div>
      <OpsPanel title="Domain readiness">
        <ul className="space-y-2 text-[12px]">
          {domains.map((d) => (
            <li
              key={str(d.domain)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2"
            >
              <Badge tone={d.ready ? "success" : "warning"}>
                {d.ready ? "ready" : "gaps"}
              </Badge>
              <span className="font-medium">{str(d.domain)}</span>
              <span className="text-[var(--fg-muted)]">
                pass {str(d.pass)} · fail {str(d.fail)} · checks {str(d.checks)}
              </span>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function QcsEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["qcs", "evidence"],
    queryFn: () => qcsApi.evidence(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Evidence unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const evidence = asRecord(asRecord(q.data).evidence);
  const packs = asList(evidence.packs).map(asRecord);
  const integrity = asRecord(evidence.integrity);

  return (
    <div className="space-y-4">
      <QcsNav />
      <IsolationBadges />
      <OpsPanel title="Evidence integrity">
        <p className="text-[12px] text-[var(--fg-muted)]">
          sources listed: {str(integrity.all_sources_listed)} · unique:{" "}
          {str(integrity.unique_source_ids)} · count:{" "}
          {str(integrity.source_count)}
        </p>
      </OpsPanel>
      <OpsPanel title="Evidence explorer">
        <ul className="space-y-2 text-[12px]">
          {packs.map((p) => (
            <li
              key={str(p.source)}
              className="border border-[var(--border)]/60 px-3 py-2"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone={p.present ? "success" : "warning"}>
                  {str(p.source).toUpperCase()}
                </Badge>
                <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                  {str(p.evidence_ref)}
                </span>
              </div>
              <p className="mt-1 text-[var(--fg-muted)]">
                {asList(p.summary_keys)
                  .map((k) => str(k))
                  .join(", ") || "no keys"}
              </p>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function QcsTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["qcs", "timeline"],
    queryFn: () => qcsApi.timeline(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Timeline unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const timeline = asList(asRecord(q.data).certification_timeline).map(
    asRecord,
  );

  return (
    <div className="space-y-4">
      <QcsNav />
      <IsolationBadges />
      <OpsPanel title="Certification timeline">
        <ul className="space-y-2 text-[12px]">
          {timeline.map((ev, i) => (
            <li
              key={`${str(ev.at)}-${i}`}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2"
            >
              <Badge tone="neutral">{str(ev.level)}</Badge>
              <span>overall {str(ev.overall)}</span>
              <span className="text-[var(--fg-muted)]">
                blockers {str(ev.blocker_count)}
              </span>
              <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                {str(ev.at)}
              </span>
            </li>
          ))}
          {!timeline.length ? (
            <li className="text-[var(--fg-muted)]">No assessments yet.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function QcsBlockersWorkspace() {
  const q = useQuery({
    queryKey: ["qcs", "blockers"],
    queryFn: () => qcsApi.blockers(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Blockers unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const blockers = asList(asRecord(q.data).blockers).map(asRecord);

  return (
    <div className="space-y-4">
      <QcsNav />
      <IsolationBadges />
      <OpsPanel title="Blocker center">
        <ul className="space-y-2 text-[12px]">
          {blockers.map((b, i) => (
            <li
              key={`${str(b.kind)}-${i}`}
              className="border border-[var(--border)]/60 px-3 py-2"
            >
              <div className="flex flex-wrap gap-2">
                <Badge
                  tone={
                    str(b.severity) === "Critical" ? "danger" : "warning"
                  }
                >
                  {str(b.severity)}
                </Badge>
                <span className="font-medium">{str(b.kind)}</span>
              </div>
              <p className="mt-1 text-[var(--fg-muted)]">{str(b.detail)}</p>
              <pre className="mt-2 max-h-24 overflow-auto text-[10px] text-[var(--fg-subtle)]">
                {JSON.stringify(b.evidence, null, 2)}
              </pre>
            </li>
          ))}
          {!blockers.length ? (
            <li className="text-[var(--fg-muted)]">No blockers.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function QcsReportsWorkspace() {
  const q = useQuery({
    queryKey: ["qcs", "reports"],
    queryFn: () => qcsApi.reports(20),
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
      <QcsNav />
      <IsolationBadges />
      <OpsPanel title="Certification reports">
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
