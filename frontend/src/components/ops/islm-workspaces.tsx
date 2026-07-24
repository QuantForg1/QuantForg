"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { islmApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/institutional-strategy-lifecycle", label: "Registry" },
  { href: "/institutional-strategy-lifecycle/timeline", label: "Timeline" },
  { href: "/institutional-strategy-lifecycle/versions", label: "Versions" },
  { href: "/institutional-strategy-lifecycle/health", label: "Health" },
  { href: "/institutional-strategy-lifecycle/evidence", label: "Evidence" },
  { href: "/institutional-strategy-lifecycle/reports", label: "Reports" },
] as const;

export function IslmNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/institutional-strategy-lifecycle"
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
      <Badge tone="neutral">STRATEGY LIFECYCLE</Badge>
      <Badge tone="success">GOVERNANCE</Badge>
      <Badge tone="warning">HUMAN APPROVAL REQUIRED</Badge>
      <Badge tone="neutral">NEVER AUTO-PROMOTE</Badge>
    </div>
  );
}

export function IslmRegistryWorkspace() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const q = useQuery({
    queryKey: ["islm", "dashboard"],
    queryFn: () => islmApi.dashboard(),
    refetchInterval: 60_000,
  });
  const approve = useMutation({
    mutationFn: islmApi.approve,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["islm"] });
    },
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "ISLM unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const registry = asList(root.registry).map(asRecord);
  const alerts = asList(root.alerts).map(asRecord);
  const active =
    registry.find((r) => str(r.strategy_id) === selected) || registry[0];

  return (
    <div className="space-y-4">
      <IslmNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Track every strategy from Draft to Retired with evidence. Transitions
        require explicit human approval. Never executes trades or modifies
        production parameters.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Strategies" value={String(registry.length)} />
        <MetricCard
          label="Alerts"
          value={String(alerts.length)}
        />
        <MetricCard
          label="Primary state"
          value={str(active?.lifecycle_state, "—")}
        />
        <MetricCard
          label="Overall health"
          value={str(
            asRecord(active?.health).overall_strategy_health,
            "—",
          )}
        />
      </div>

      <OpsPanel title="Strategy registry">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12px]">
            <thead className="text-[var(--fg-muted)]">
              <tr className="border-b border-[var(--border)]">
                <th className="py-2 pr-3 font-medium">ID</th>
                <th className="py-2 pr-3 font-medium">Name</th>
                <th className="py-2 pr-3 font-medium">Owner</th>
                <th className="py-2 pr-3 font-medium">Version</th>
                <th className="py-2 pr-3 font-medium">Lifecycle</th>
                <th className="py-2 font-medium">Health</th>
              </tr>
            </thead>
            <tbody>
              {registry.map((row) => (
                <tr
                  key={str(row.strategy_id)}
                  className={cn(
                    "cursor-pointer border-b border-[var(--border)]/50",
                    str(row.strategy_id) === str(active?.strategy_id) &&
                      "bg-[var(--surface-2)]",
                  )}
                  onClick={() => setSelected(str(row.strategy_id))}
                >
                  <td className="py-2 pr-3 font-mono text-[11px]">
                    {str(row.strategy_id)}
                  </td>
                  <td className="py-2 pr-3">{str(row.name)}</td>
                  <td className="py-2 pr-3">{str(row.owner)}</td>
                  <td className="py-2 pr-3">{str(row.version)}</td>
                  <td className="py-2 pr-3">{str(row.lifecycle_state)}</td>
                  <td className="py-2">
                    {str(
                      asRecord(row.health).overall_strategy_health,
                      "—",
                    )}
                  </td>
                </tr>
              ))}
              {!registry.length ? (
                <tr>
                  <td
                    colSpan={6}
                    className="py-4 text-[var(--fg-muted)]"
                  >
                    No strategies in registry yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </OpsPanel>

      {active ? (
        <OpsPanel title="Human lifecycle approval">
          <p className="mb-3 text-[11px] text-[var(--fg-subtle)]">
            Current: {str(active.lifecycle_state)} → recommended next:{" "}
            {str(active.recommended_next_state, "none")}. Auto-promotion
            disabled.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={
                !active.recommended_next_state || approve.isPending
              }
              onClick={() =>
                approve.mutate({
                  strategy_id: str(active.strategy_id),
                  to_state: str(active.recommended_next_state),
                  decision: "approved",
                  comment: "Explicit human advance",
                })
              }
            >
              Approve next state
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={approve.isPending}
              onClick={() =>
                approve.mutate({
                  strategy_id: str(active.strategy_id),
                  to_state: str(active.lifecycle_state),
                  decision: "rejected",
                  comment: "Human rejected advance",
                })
              }
            >
              Reject advance
            </Button>
          </div>
          {approve.isError ? (
            <p className="mt-2 text-[12px] text-[var(--danger)]">
              {approve.error instanceof Error
                ? approve.error.message
                : "Approval failed"}
            </p>
          ) : null}
        </OpsPanel>
      ) : null}

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
              No lifecycle alerts in current snapshot.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IslmTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["islm", "timeline"],
    queryFn: () => islmApi.timeline(),
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
  const root = asRecord(q.data);
  const timeline = asList(root.lifecycle_timeline).map(asRecord);

  return (
    <div className="space-y-4">
      <IslmNav />
      <IsolationBadges />
      <OpsPanel title="Lifecycle timeline">
        <ol className="space-y-2">
          {timeline.map((ev, i) => (
            <li
              key={`${str(ev.stage)}-${i}`}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge
                tone={
                  str(ev.status) === "current"
                    ? "success"
                    : str(ev.status) === "completed"
                      ? "neutral"
                      : "warning"
                }
              >
                {str(ev.status)}
              </Badge>
              <span className="font-medium">{str(ev.stage)}</span>
              {ev.requires_human_approval ? (
                <span className="text-[var(--fg-subtle)]">
                  human approval required
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      </OpsPanel>
    </div>
  );
}

export function IslmVersionsWorkspace() {
  const q = useQuery({
    queryKey: ["islm", "versions"],
    queryFn: () => islmApi.versions(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Versions unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const explorer = asList(asRecord(q.data).version_explorer).map(asRecord);

  return (
    <div className="space-y-4">
      <IslmNav />
      <IsolationBadges />
      <OpsPanel title="Version explorer">
        <ul className="space-y-3">
          {explorer.map((row) => (
            <li
              key={str(row.strategy_id)}
              className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <div className="mb-1 flex flex-wrap gap-2">
                <span className="font-mono">{str(row.strategy_id)}</span>
                <Badge tone="neutral">{str(row.version, "—")}</Badge>
              </div>
              <ul className="space-y-1 text-[var(--fg-muted)]">
                {asList(row.history)
                  .map(asRecord)
                  .map((h, i) => (
                    <li key={i}>
                      {str(h.at)} · {str(h.from, "")}
                      {h.from ? " → " : ""}
                      {str(h.to || h.lifecycle_state || h.note)}
                      {h.approver ? ` · ${str(h.approver)}` : ""}
                    </li>
                  ))}
                {!asList(row.history).length ? (
                  <li>No version events yet.</li>
                ) : null}
              </ul>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IslmHealthWorkspace() {
  const q = useQuery({
    queryKey: ["islm", "health"],
    queryFn: () => islmApi.health(),
  });
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Health unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const dash = asRecord(asRecord(q.data).health_dashboard);
  const primary = asRecord(dash.primary);
  const registry = asList(dash.registry).map(asRecord);

  return (
    <div className="space-y-4">
      <IslmNav />
      <IsolationBadges />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <MetricCard
          label="Research"
          value={str(primary.research_score, "—")}
        />
        <MetricCard
          label="Validation"
          value={str(primary.validation_score, "—")}
        />
        <MetricCard
          label="Execution"
          value={str(primary.execution_score, "—")}
        />
        <MetricCard
          label="Reliability"
          value={str(primary.reliability_score, "—")}
        />
        <MetricCard label="Risk" value={str(primary.risk_score, "—")} />
        <MetricCard
          label="Overall"
          value={str(primary.overall_strategy_health, "—")}
        />
      </div>
      <OpsPanel title="Registry health">
        <ul className="space-y-2 text-[12px]">
          {registry.map((r) => {
            const h = asRecord(r.health);
            return (
              <li
                key={str(r.strategy_id)}
                className="flex flex-wrap gap-3 border border-[var(--border)]/60 px-3 py-2"
              >
                <span className="font-mono">{str(r.strategy_id)}</span>
                <span>overall {str(h.overall_strategy_health, "—")}</span>
              </li>
            );
          })}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IslmEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["islm", "evidence"],
    queryFn: () => islmApi.evidence(),
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
  const evidence = asRecord(asRecord(q.data).evidence_viewer);

  const blocks = [
    ["Research history", asList(evidence.research_history)],
    ["Replay results", asList(evidence.replay_results)],
    ["Simulation results", asList(evidence.simulation_results)],
    ["Release history", asList(evidence.release_history)],
    ["QKG links", asList(evidence.knowledge_graph_links)],
  ] as const;

  return (
    <div className="space-y-4">
      <IslmNav />
      <IsolationBadges />
      <div className="grid gap-3 lg:grid-cols-2">
        {blocks.map(([title, rows]) => (
          <OpsPanel key={title} title={title}>
            <ul className="max-h-56 space-y-1 overflow-auto text-[11px] text-[var(--fg-muted)]">
              {rows.slice(0, 20).map((row, i) => (
                <li key={i} className="font-mono">
                  {JSON.stringify(row)}
                </li>
              ))}
              {!rows.length ? <li>No evidence in this bucket.</li> : null}
            </ul>
          </OpsPanel>
        ))}
      </div>
      <OpsPanel title="CVF / Risk / EQS / RES snapshots">
        <pre className="max-h-72 overflow-auto text-[11px] text-[var(--fg-muted)]">
          {JSON.stringify(
            {
              cvf_findings: evidence.cvf_findings,
              risk_analytics: evidence.risk_analytics,
              execution_quality: evidence.execution_quality,
              reliability: evidence.reliability,
            },
            null,
            2,
          )}
        </pre>
      </OpsPanel>
    </div>
  );
}

export function IslmReportsWorkspace() {
  const q = useQuery({
    queryKey: ["islm", "reports"],
    queryFn: () => islmApi.reports(20),
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
      <IslmNav />
      <IsolationBadges />
      <OpsPanel title="Lifecycle reports">
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
                <span className="text-[var(--fg-muted)]">
                  {str(r.created_at)}
                </span>
              </div>
              <p className="mt-1 text-[var(--fg-muted)]">{str(r.title)}</p>
            </li>
          ))}
          {!reports.length ? (
            <li className="text-[var(--fg-muted)]">No reports persisted yet.</li>
          ) : null}
        </ul>
      </OpsPanel>
    </div>
  );
}
