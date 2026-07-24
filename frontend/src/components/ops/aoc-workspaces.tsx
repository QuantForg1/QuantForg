"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { aocApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-operations-center", label: "Dashboard" },
  {
    href: "/quantforg-operations-center/recommendations",
    label: "Recommendations",
  },
  { href: "/quantforg-operations-center/queue", label: "Queue" },
  { href: "/quantforg-operations-center/brief", label: "Executive Brief" },
  { href: "/quantforg-operations-center/evidence", label: "Evidence" },
  { href: "/quantforg-operations-center/reports", label: "Reports" },
] as const;

export function AocNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-operations-center"
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
      <Badge tone="neutral">OPERATIONS CENTER</Badge>
      <Badge tone="success">READ-ONLY</Badge>
      <Badge tone="warning">HUMAN APPROVAL REQUIRED</Badge>
      <Badge tone="neutral">NO AUTO-REMEDIATION</Badge>
    </div>
  );
}

function priorityTone(p: string): "danger" | "warning" | "neutral" | "success" {
  if (p === "P0") return "danger";
  if (p === "P1") return "warning";
  if (p === "P2") return "neutral";
  return "success";
}

export function AocDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["aoc", "dashboard"],
    queryFn: () => aocApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "AOC unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const scores = asRecord(root.executive_scores);
  const health = asRecord(root.operational_health);
  const queue = asList(root.work_queue).map(asRecord);

  return (
    <div className="space-y-4">
      <AocNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Unified operational orchestration. Prioritizes work and recommends
        actions — never remediates, deploys, or modifies production.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          label="Platform"
          value={str(scores.platform_readiness, "—")}
        />
        <MetricCard
          label="Research"
          value={str(scores.research_readiness, "—")}
        />
        <MetricCard
          label="Release"
          value={str(scores.release_readiness, "—")}
        />
        <MetricCard
          label="Portfolio"
          value={str(scores.portfolio_readiness, "—")}
        />
        <MetricCard
          label="Operational"
          value={str(scores.operational_readiness, "—")}
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard
          label="Ops health"
          value={str(health.overall_operational_health, "—")}
        />
        <MetricCard label="Queue items" value={String(queue.length)} />
        <MetricCard
          label="Sources"
          value={str(health.source_count, "—")}
        />
      </div>
      <OpsPanel title="Queue preview">
        <ul className="space-y-2">
          {queue.slice(0, 8).map((item) => (
            <li
              key={str(item.item_id)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone={priorityTone(str(item.priority))}>
                {str(item.priority)}
              </Badge>
              <span className="font-medium">{str(item.kind)}</span>
              <span className="text-[var(--fg-muted)]">{str(item.detail)}</span>
            </li>
          ))}
          {!queue.length ? (
            <li className="text-[12px] text-[var(--fg-muted)]">
              Queue empty.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AocRecommendationsWorkspace() {
  const q = useQuery({
    queryKey: ["aoc", "recommendations"],
    queryFn: () => aocApi.recommendations(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Recommendations unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const recommendations = asList(asRecord(q.data).recommendations).map(
    asRecord,
  );

  return (
    <div className="space-y-4">
      <AocNav />
      <IsolationBadges />
      <OpsPanel title="Recommendation center">
        <ul className="space-y-2 text-[12px]">
          {recommendations.map((r) => (
            <li
              key={str(r.recommendation_id)}
              className="border border-[var(--border)]/60 px-3 py-2"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone={priorityTone(str(r.priority))}>
                  {str(r.priority)}
                </Badge>
                <Badge tone="neutral">{str(r.kind)}</Badge>
                <span className="text-[var(--fg-muted)]">
                  {str(r.category)} · {str(r.owner)}
                </span>
              </div>
              <p className="mt-1">{str(r.detail)}</p>
              <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">
                Next: {str(r.suggested_next_action)}
              </p>
            </li>
          ))}
          {!recommendations.length ? (
            <li className="text-[var(--fg-muted)]">No recommendations.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AocQueueWorkspace() {
  const q = useQuery({
    queryKey: ["aoc", "queue"],
    queryFn: () => aocApi.queue(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Queue unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const queue = asList(asRecord(q.data).work_queue).map(asRecord);

  return (
    <div className="space-y-4">
      <AocNav />
      <IsolationBadges />
      <OpsPanel title="Operational queue">
        <ul className="space-y-2 text-[12px]">
          {queue.map((item) => (
            <li
              key={str(item.item_id)}
              className="border border-[var(--border)]/60 px-3 py-2"
            >
              <div className="flex flex-wrap gap-2">
                <Badge tone="neutral">#{str(item.queue_position)}</Badge>
                <Badge tone={priorityTone(str(item.priority))}>
                  {str(item.priority)}
                </Badge>
                <span className="font-medium">{str(item.kind)}</span>
              </div>
              <p className="mt-1 text-[var(--fg-muted)]">{str(item.detail)}</p>
              <p className="mt-1 text-[11px]">
                Owner {str(item.owner)} · deps{" "}
                {asList(item.dependencies)
                  .map((d) => str(d))
                  .join(", ") || "—"}
              </p>
              <p className="text-[11px] text-[var(--fg-subtle)]">
                {str(item.suggested_next_action)}
              </p>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AocBriefWorkspace() {
  const q = useQuery({
    queryKey: ["aoc", "brief"],
    queryFn: () => aocApi.brief(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Brief unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const brief = asRecord(asRecord(q.data).executive_brief);
  const scores = asRecord(brief.scores);
  const watches = asRecord(brief.watches);

  return (
    <div className="space-y-4">
      <AocNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {(
          [
            ["Platform", "platform_readiness"],
            ["Research", "research_readiness"],
            ["Release", "release_readiness"],
            ["Portfolio", "portfolio_readiness"],
            ["Operational", "operational_readiness"],
          ] as const
        ).map(([label, key]) => (
          <MetricCard key={key} label={label} value={str(scores[key], "—")} />
        ))}
      </div>
      <OpsPanel title="Watch summary">
        <pre className="max-h-80 overflow-auto text-[11px] text-[var(--fg-muted)]">
          {JSON.stringify(watches, null, 2)}
        </pre>
      </OpsPanel>
    </div>
  );
}

export function AocEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["aoc", "evidence"],
    queryFn: () => aocApi.evidence(),
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
      <AocNav />
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
              <Badge tone={p.present ? "success" : "warning"}>
                {str(p.source).toUpperCase()}
              </Badge>
              <span className="ml-2 font-mono text-[10px] text-[var(--fg-subtle)]">
                {str(p.evidence_ref)}
              </span>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function AocReportsWorkspace() {
  const q = useQuery({
    queryKey: ["aoc", "reports"],
    queryFn: () => aocApi.reports(20),
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
      <AocNav />
      <IsolationBadges />
      <OpsPanel title="Operations reports">
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
