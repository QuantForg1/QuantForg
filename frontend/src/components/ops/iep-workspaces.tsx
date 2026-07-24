"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iepApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/institutional-experimentation", label: "Registry" },
  { href: "/institutional-experimentation/hypothesis", label: "Hypothesis" },
  { href: "/institutional-experimentation/comparison", label: "Comparison" },
  { href: "/institutional-experimentation/evidence", label: "Evidence" },
  { href: "/institutional-experimentation/decisions", label: "Decisions" },
  { href: "/institutional-experimentation/reports", label: "Reports" },
] as const;

export function IepNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/institutional-experimentation"
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
      <Badge tone="neutral">EXPERIMENTATION PLATFORM</Badge>
      <Badge tone="success">READ-ONLY</Badge>
      <Badge tone="warning">NEVER AUTO-PROMOTE</Badge>
      <Badge tone="neutral">HUMAN DECISION</Badge>
    </div>
  );
}

export function IepRegistryWorkspace() {
  const q = useQuery({
    queryKey: ["iep", "dashboard"],
    queryFn: () => iepApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "IEP unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const registry = asList(root.registry).map(asRecord);
  const primary = registry[0];
  const stats = asRecord(primary?.statistics);

  return (
    <div className="space-y-4">
      <IepNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Governed research experiments from Idea to Archive. Never executes
        trades, modifies production, or promotes automatically.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Experiments" value={String(registry.length)} />
        <MetricCard
          label="Primary stage"
          value={str(primary?.lifecycle_state, "—")}
        />
        <MetricCard label="P-value" value={str(stats.p_value, "—")} />
        <MetricCard
          label="Generalization"
          value={str(stats.generalization_score, "—")}
        />
      </div>
      <OpsPanel title="Experiment registry">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <thead className="text-[var(--fg-muted)]">
              <tr className="border-b border-[var(--border)]">
                <th className="py-2 pr-3 font-medium">ID</th>
                <th className="py-2 pr-3 font-medium">Title</th>
                <th className="py-2 pr-3 font-medium">Lifecycle</th>
                <th className="py-2 pr-3 font-medium">Owner</th>
                <th className="py-2 font-medium">Decision</th>
              </tr>
            </thead>
            <tbody>
              {registry.map((row) => (
                <tr
                  key={str(row.experiment_id)}
                  className="border-b border-[var(--border)]/50"
                >
                  <td className="py-2 pr-3 font-mono text-[11px]">
                    {str(row.experiment_id)}
                  </td>
                  <td className="py-2 pr-3">{str(row.title)}</td>
                  <td className="py-2 pr-3">{str(row.lifecycle_state)}</td>
                  <td className="py-2 pr-3">{str(row.owner)}</td>
                  <td className="py-2">{str(row.recommended_decision)}</td>
                </tr>
              ))}
              {!registry.length ? (
                <tr>
                  <td colSpan={5} className="py-4 text-[var(--fg-muted)]">
                    No experiments in registry.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </OpsPanel>
    </div>
  );
}

export function IepHypothesisWorkspace() {
  const q = useQuery({
    queryKey: ["iep", "hypothesis"],
    queryFn: () => iepApi.hypothesis(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Hypothesis unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const builder = asRecord(asRecord(q.data).hypothesis_builder);
  const scaffolds = asList(builder.scaffolds).map(asRecord);

  return (
    <div className="space-y-4">
      <IepNav />
      <IsolationBadges />
      <OpsPanel title="Hypothesis builder (research scaffolds)">
        <ul className="space-y-3">
          {scaffolds.map((s) => (
            <li
              key={str(s.experiment_id)}
              className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <div className="mb-1 font-mono text-[11px]">
                {str(s.experiment_id)}
              </div>
              <p className="text-[var(--fg)]">{str(s.hypothesis)}</p>
              <p className="mt-1 text-[var(--fg-muted)]">
                Variables:{" "}
                {asList(s.variables)
                  .map((v) => str(v))
                  .join(", ") || "—"}
              </p>
              <Badge tone="neutral">{str(s.lifecycle_state)}</Badge>
            </li>
          ))}
          {!scaffolds.length ? (
            <li className="text-[var(--fg-muted)]">No hypothesis scaffolds.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IepComparisonWorkspace() {
  const q = useQuery({
    queryKey: ["iep", "comparison"],
    queryFn: () => iepApi.comparison(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Comparison unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const ws = asRecord(asRecord(q.data).comparison_workspace);
  const ranked = asList(ws.ranked_by_evidence).map(asRecord);

  return (
    <div className="space-y-4">
      <IepNav />
      <IsolationBadges />
      <OpsPanel title="Comparison workspace — ranked by evidence">
        <ul className="space-y-2">
          {ranked.map((r) => {
            const st = asRecord(r.statistics);
            return (
              <li
                key={`${str(r.label)}-${str(r.source_id)}`}
                className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
              >
                <Badge tone="neutral">#{str(r.rank)}</Badge>
                <span className="font-medium">{str(r.label)}</span>
                <span>{str(r.name)}</span>
                <span className="text-[var(--fg-muted)]">
                  metric {str(r.metric, "—")} · evidence{" "}
                  {str(r.evidence_rank_score, "—")}
                </span>
                {st.p_value != null ? (
                  <span className="text-[var(--fg-subtle)]">
                    p={str(st.p_value)}
                  </span>
                ) : null}
              </li>
            );
          })}
          {!ranked.length ? (
            <li className="text-[var(--fg-muted)]">No variants to compare.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IepEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["iep", "evidence"],
    queryFn: () => iepApi.evidence(),
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
  const evidence = asRecord(asRecord(q.data).evidence_explorer);
  const stats = asRecord(evidence.statistics);

  return (
    <div className="space-y-4">
      <IepNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard label="P-value" value={str(stats.p_value, "—")} />
        <MetricCard
          label="Effect size"
          value={str(stats.effect_size, "—")}
        />
        <MetricCard label="Sample size" value={str(stats.sample_size, "—")} />
        <MetricCard
          label="Power"
          value={str(stats.statistical_power, "—")}
        />
        <MetricCard
          label="Generalization"
          value={str(stats.generalization_score, "—")}
        />
        <MetricCard
          label="CI"
          value={
            asRecord(stats.confidence_interval).low != null
              ? `${str(asRecord(stats.confidence_interval).low)} … ${str(asRecord(stats.confidence_interval).high)}`
              : "—"
          }
        />
      </div>
      <OpsPanel title="Evidence explorer">
        <pre className="max-h-96 overflow-auto text-[11px] text-[var(--fg-muted)]">
          {JSON.stringify(evidence, null, 2)}
        </pre>
      </OpsPanel>
    </div>
  );
}

export function IepDecisionsWorkspace() {
  const q = useQuery({
    queryKey: ["iep", "decisions"],
    queryFn: () => iepApi.decisions(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Decisions unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const dash = asRecord(asRecord(q.data).decision_dashboard);
  const pending = asList(dash.pending_human_decisions).map(asRecord);

  return (
    <div className="space-y-4">
      <IepNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard
          label="Pending human"
          value={String(pending.length)}
        />
        <MetricCard
          label="Archived"
          value={str(dash.archived_count, "0")}
        />
        <MetricCard
          label="Total"
          value={str(dash.total_experiments, "0")}
        />
      </div>
      <OpsPanel title="Decision dashboard">
        <p className="mb-3 text-[11px] text-[var(--fg-subtle)]">
          {str(dash.note)} Auto-approve and auto-promote are disabled.
        </p>
        <ul className="space-y-2 text-[12px]">
          {pending.map((p) => (
            <li
              key={str(p.experiment_id)}
              className="border border-[var(--border)]/60 px-3 py-2"
            >
              <div className="flex flex-wrap gap-2">
                <span className="font-mono text-[11px]">
                  {str(p.experiment_id)}
                </span>
                <Badge tone="warning">{str(p.lifecycle_state)}</Badge>
              </div>
              <p className="mt-1">{str(p.title)}</p>
              <p className="text-[var(--fg-muted)]">
                {str(p.recommended_decision)}
              </p>
            </li>
          ))}
          {!pending.length ? (
            <li className="text-[var(--fg-muted)]">
              No experiments awaiting human decision.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IepReportsWorkspace() {
  const q = useQuery({
    queryKey: ["iep", "reports"],
    queryFn: () => iepApi.reports(20),
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
      <IepNav />
      <IsolationBadges />
      <OpsPanel title="Experiment reports">
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
