"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qsfApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-strategy-factory", label: "Dashboard" },
  { href: "/quantforg-strategy-factory/pipeline", label: "Pipeline" },
  { href: "/quantforg-strategy-factory/workspace", label: "Workspace" },
  { href: "/quantforg-strategy-factory/evidence", label: "Evidence" },
  { href: "/quantforg-strategy-factory/approvals", label: "Approvals" },
  { href: "/quantforg-strategy-factory/reports", label: "Reports" },
] as const;

export function QsfNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-strategy-factory"
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
      <Badge tone="neutral">STRATEGY FACTORY</Badge>
      <Badge tone="success">HUMAN-GATED</Badge>
      <Badge tone="warning">NO DEPLOY / NO LIVE</Badge>
      <Badge tone="neutral">SAFETY PRESERVED</Badge>
    </div>
  );
}

export function QsfDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["qsf", "dashboard"],
    queryFn: () => qsfApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "QSF unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const sections = asRecord(root.sections);
  const dash = asRecord(sections.factory_dashboard);
  const counts = asRecord(dash.stage_counts);

  return (
    <div className="space-y-4">
      <QsfNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        End-to-end strategy development workflow. Transitions require explicit
        human approval — never deploys, trades, or allocates capital.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Work items"
          value={str(dash.work_item_count, "—")}
        />
        <MetricCard label="Queue" value={str(dash.queue_depth, "—")} />
        <MetricCard
          label="Validation"
          value={str(counts["Continuous Validation"], "0")}
        />
        <MetricCard
          label="Paper ready"
          value={str(counts["Paper Trading Ready"], "0")}
        />
      </div>
      <OpsPanel title="Pipeline snapshot">
        <div className="flex flex-wrap gap-2">
          {Object.entries(counts).map(([stage, n]) => (
            <span
              key={stage}
              className="border border-[var(--border)] px-2 py-1 font-mono text-[10px] text-[var(--fg-muted)]"
            >
              {stage}: {str(n)}
            </span>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QsfPipelineWorkspace() {
  const q = useQuery({
    queryKey: ["qsf", "pipeline"],
    queryFn: () => qsfApi.pipeline(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Pipeline unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const board = asRecord(asRecord(q.data).pipeline_board);
  const stages = asList(board.stages).map((s) => str(s));
  const columns = asRecord(board.columns);

  return (
    <div className="space-y-4">
      <QsfNav />
      <IsolationBadges />
      <OpsPanel title="Pipeline Board">
        <div className="flex gap-2 overflow-x-auto pb-2">
          {stages.map((stage) => {
            const cards = asList(columns[stage]).map(asRecord);
            return (
              <div
                key={stage}
                className="min-w-[160px] flex-shrink-0 border border-[var(--border)] bg-[var(--surface-1)]"
              >
                <div className="border-b border-[var(--border)] px-2 py-1.5 text-[10px] uppercase tracking-[0.08em] text-[var(--fg-muted)]">
                  {stage} · {cards.length}
                </div>
                <div className="max-h-[420px] space-y-1 overflow-y-auto p-2">
                  {cards.length === 0 ? (
                    <p className="text-[10px] text-[var(--fg-subtle)]">Empty</p>
                  ) : (
                    cards.map((c) => (
                      <div
                        key={str(c.work_item_id)}
                        className="border border-[var(--border)] px-2 py-1.5"
                      >
                        <div className="font-mono text-[10px] text-[var(--fg)]">
                          {str(c.name || c.strategy_id || "—")}
                        </div>
                        <div className="text-[10px] text-[var(--fg-muted)]">
                          {str(c.owner)} · {str(c.status)}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QsfWorkspacePanel() {
  const q = useQuery({
    queryKey: ["qsf", "work-items"],
    queryFn: () => qsfApi.workItems(),
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Workspace unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const items = asList(asRecord(q.data).work_items).map(asRecord);

  return (
    <div className="space-y-4">
      <QsfNav />
      <IsolationBadges />
      <OpsPanel title="Strategy Workspace">
        <div className="max-h-[520px] space-y-2 overflow-y-auto">
          {items.map((w) => (
            <div
              key={str(w.work_item_id)}
              className="border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2"
            >
              <div className="text-[13px] text-[var(--fg)]">{str(w.title)}</div>
              <div className="mt-1 text-[11px] text-[var(--fg-muted)]">
                {str(w.pipeline_stage)} → {str(w.next_stage, "complete")} ·{" "}
                {str(w.owner)} · {str(w.status)}
              </div>
              <div className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                target {str(w.target_completion)} · deps{" "}
                {asList(w.dependencies)
                  .map((d) => str(d))
                  .join(", ")}
              </div>
            </div>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QsfEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["qsf", "dossiers"],
    queryFn: () => qsfApi.dossiers(),
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
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
  const root = asRecord(asRecord(q.data).dossiers);
  const dossiers = asRecord(root.dossiers);
  const kinds = asList(root.kinds).map((k) => str(k));

  return (
    <div className="space-y-4">
      <QsfNav />
      <IsolationBadges />
      <OpsPanel title="Evidence Center">
        <div className="space-y-4">
          {kinds.map((kind) => {
            const rows = asList(dossiers[kind]).map(asRecord);
            return (
              <div key={kind}>
                <div className="mb-1 text-[11px] uppercase tracking-[0.08em] text-[var(--fg-muted)]">
                  {kind.replaceAll("_", " ")} · {rows.length}
                </div>
                <div className="max-h-[160px] space-y-1 overflow-y-auto">
                  {rows.slice(0, 8).map((r) => (
                    <div
                      key={`${kind}-${str(r.strategy_id)}`}
                      className="border border-[var(--border)] px-2 py-1 font-mono text-[11px] text-[var(--fg)]"
                    >
                      {str(r.name)} · {str(r.pipeline_stage)}
                    </div>
                  ))}
                  {rows.length === 0 ? (
                    <p className="text-[11px] text-[var(--fg-subtle)]">
                      No dossiers.
                    </p>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QsfApprovalsWorkspace() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const q = useQuery({
    queryKey: ["qsf", "approvals"],
    queryFn: () => qsfApi.approvals(),
    refetchInterval: 30_000,
  });
  const mutate = useMutation({
    mutationFn: qsfApi.approve,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["qsf"] });
      setBusy(null);
    },
    onError: () => setBusy(null),
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Approvals unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const queue = asList(asRecord(q.data).approval_queue).map(asRecord);
  const history = asList(asRecord(q.data).approvals).map(asRecord);

  return (
    <div className="space-y-4">
      <QsfNav />
      <IsolationBadges />
      <OpsPanel title="Approval Queue">
        <div className="max-h-[360px] space-y-2 overflow-y-auto">
          {queue.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No pending human approvals.
            </p>
          ) : (
            queue.map((item) => (
              <div
                key={str(item.queue_id)}
                className="border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2"
              >
                <div className="text-[13px] text-[var(--fg)]">
                  {str(item.title)}
                </div>
                <div className="mt-1 text-[11px] text-[var(--fg-muted)]">
                  {str(item.from_stage)} → {str(item.to_stage)} ·{" "}
                  {str(item.strategy_id)}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy === str(item.queue_id)}
                    className="border border-[var(--border-strong)] px-2 py-1 text-[11px] uppercase tracking-[0.08em] text-[var(--fg)]"
                    onClick={() => {
                      setBusy(str(item.queue_id));
                      mutate.mutate({
                        strategy_id: str(item.strategy_id),
                        to_stage: str(item.to_stage),
                        decision: "approved",
                        work_item_id: str(item.work_item_id),
                      });
                    }}
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    disabled={busy === str(item.queue_id)}
                    className="border border-[var(--border)] px-2 py-1 text-[11px] uppercase tracking-[0.08em] text-[var(--fg-muted)]"
                    onClick={() => {
                      setBusy(str(item.queue_id));
                      mutate.mutate({
                        strategy_id: str(item.strategy_id),
                        to_stage: str(item.to_stage),
                        decision: "rejected",
                        work_item_id: str(item.work_item_id),
                      });
                    }}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
        {mutate.isError ? (
          <p className="mt-2 text-[11px] text-[var(--danger)]">
            {mutate.error instanceof Error
              ? mutate.error.message
              : "Approval failed"}
          </p>
        ) : null}
      </OpsPanel>
      <OpsPanel title="Approval history">
        <div className="max-h-[200px] space-y-1 overflow-y-auto font-mono text-[11px]">
          {history.map((h) => (
            <div
              key={str(h.approval_id)}
              className="border-b border-[var(--border)] py-1 text-[var(--fg)]"
            >
              {str(h.created_at)} · {str(h.decision)} · {str(h.strategy_id)} ·{" "}
              {str(h.from_stage)}→{str(h.to_stage)}
            </div>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QsfReportsWorkspace() {
  const q = useQuery({
    queryKey: ["qsf", "reports"],
    queryFn: () => qsfApi.reports(20),
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
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
      <QsfNav />
      <IsolationBadges />
      <OpsPanel title="Reports">
        <div className="max-h-[520px] space-y-2 overflow-y-auto">
          {reports.map((r) => (
            <div
              key={str(r.report_id)}
              className="border border-[var(--border)] px-3 py-2"
            >
              <div className="font-mono text-[12px] text-[var(--fg)]">
                {str(r.kind)} · {str(r.report_id)}
              </div>
              <div className="text-[10px] text-[var(--fg-subtle)]">
                {str(r.recorded_at)}
              </div>
            </div>
          ))}
          {reports.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">No reports yet.</p>
          ) : null}
        </div>
      </OpsPanel>
    </div>
  );
}
