"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { irdpApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/institutional-release", label: "Dashboard" },
  { href: "/institutional-release/timeline", label: "Timeline" },
  { href: "/institutional-release/approvals", label: "Approvals" },
  { href: "/institutional-release/rollbacks", label: "Rollbacks" },
  { href: "/institutional-release/reports", label: "Reports" },
] as const;

export function IrdpNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/institutional-release"
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

function useIrdpDashboard() {
  return useQuery({
    queryKey: ["irdp", "dashboard"],
    queryFn: () => irdpApi.dashboard(),
    refetchInterval: 60_000,
  });
}

export function IrdpDashboardWorkspace() {
  const q = useIrdpDashboard();
  const qc = useQueryClient();
  const [version, setVersion] = useState("v3.0.0-rc2");
  const create = useMutation({
    mutationFn: () => irdpApi.createRelease({ version }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["irdp"] }),
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "IRDP unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const monitoring = asRecord(root.monitoring);
  const checklist = asList(root.checklist).map(asRecord);
  const awaiting = asList(root.awaiting_approval).map(asRecord);

  return (
    <div className="space-y-4">
      <IrdpNav />
      <div className="flex flex-wrap gap-2">
        <Badge tone="neutral">RELEASE & DEPLOYMENT</Badge>
        <Badge tone="success">HUMAN APPROVAL</Badge>
        <Badge tone="warning">NEVER AUTO-APPROVES</Badge>
        <Badge tone="warning">NEVER EXECUTES</Badge>
      </div>
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Institutional release governance from development through post-release
        monitoring. Every production step requires explicit human approval.
      </p>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Release health"
          value={str(monitoring.release_health_score, "—")}
        />
        <MetricCard
          label="Checklist pass"
          value={`${str(root.checklist_pass_count)}/${str(root.checklist_total)}`}
        />
        <MetricCard
          label="Awaiting approval"
          value={String(awaiting.length)}
        />
        <MetricCard
          label="Releases"
          value={String(asList(root.releases).length)}
        />
      </div>

      <OpsPanel title="Create draft release">
        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            aria-label="Version"
            className="flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px]"
            value={version}
            onChange={(e) => setVersion(e.target.value)}
          />
          <Button
            size="sm"
            variant="secondary"
            disabled={create.isPending || !version.trim()}
            onClick={() => create.mutate()}
          >
            Create draft
          </Button>
        </div>
      </OpsPanel>

      <OpsPanel title="Release checklist">
        <ul className="space-y-2">
          {checklist.map((c) => (
            <li
              key={str(c.item)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone={c.passed ? "success" : "warning"}>
                {str(c.status)}
              </Badge>
              <span className="font-medium">{str(c.item)}</span>
              <span className="text-[var(--fg-muted)]">{str(c.detail)}</span>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IrdpTimelineWorkspace() {
  const q = useIrdpDashboard();
  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={q.error instanceof Error ? q.error.message : "Unavailable"}
        onRetry={() => void q.refetch()}
      />
    );
  }
  const releases = asList(asRecord(q.data).releases).map(asRecord);
  const latest = releases[0] || {};
  const timeline = asList(latest.timeline).map(asRecord);
  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: () => irdpApi.advance(str(latest.release_id)),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["irdp"] }),
  });

  return (
    <div className="space-y-4">
      <IrdpNav />
      <OpsPanel title="Release timeline">
        <p className="mb-3 text-[12px] text-[var(--fg-muted)]">
          {str(latest.version)} · {str(latest.status)} · commit{" "}
          {str(latest.commit_hash, "—")}
        </p>
        <ol className="space-y-2 border-l border-[var(--border)] pl-3">
          {timeline.map((s) => (
            <li key={str(s.stage)} className="text-[12px]">
              <Badge
                tone={
                  str(s.state) === "current"
                    ? "warning"
                    : str(s.state) === "completed"
                      ? "success"
                      : "neutral"
                }
              >
                {str(s.state)}
              </Badge>{" "}
              {str(s.stage)}
              {s.requires_human_approval ? (
                <span className="text-[var(--fg-muted)]"> · human gate</span>
              ) : null}
            </li>
          ))}
        </ol>
        {latest.release_id ? (
          <div className="mt-3">
            <Button
              size="sm"
              variant="secondary"
              disabled={advance.isPending}
              onClick={() => advance.mutate()}
            >
              Advance stage
            </Button>
          </div>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function IrdpApprovalsWorkspace() {
  const q = useIrdpDashboard();
  const qc = useQueryClient();
  const [approver, setApprover] = useState("release-officer");
  const [comment, setComment] = useState("");
  const awaiting = asList(asRecord(q.data).awaiting_approval).map(asRecord);
  const history = asList(asRecord(q.data).approvals).map(asRecord);
  const approve = useMutation({
    mutationFn: (args: { id: string; decision: string }) =>
      irdpApi.approve(args.id, {
        approver,
        decision: args.decision,
        comment: comment || undefined,
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["irdp"] }),
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

  return (
    <div className="space-y-4">
      <IrdpNav />
      <OpsPanel title="Approval workspace">
        <p className="mb-3 text-[11px] text-[var(--fg-subtle)]">
          Explicit human decision required. IRDP never auto-approves.
        </p>
        <div className="mb-3 flex flex-col gap-2 sm:flex-row">
          <input
            aria-label="Approver"
            className="flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px]"
            value={approver}
            onChange={(e) => setApprover(e.target.value)}
            placeholder="Approver"
          />
          <input
            aria-label="Comment"
            className="flex-1 border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px]"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Comment"
          />
        </div>
        <ul className="space-y-3">
          {awaiting.map((r) => (
            <li
              key={str(r.release_id)}
              className="border border-[var(--border)] px-3 py-3 text-[12px]"
            >
              <div className="mb-2 flex flex-wrap gap-2">
                <Badge tone="warning">{str(r.status)}</Badge>
                <span className="font-medium">{str(r.version)}</span>
                <span className="text-[var(--fg-muted)]">
                  {str(r.release_id)}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={approve.isPending || !approver.trim()}
                  onClick={() =>
                    approve.mutate({
                      id: str(r.release_id),
                      decision: "approve",
                    })
                  }
                >
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={approve.isPending || !approver.trim()}
                  onClick={() =>
                    approve.mutate({
                      id: str(r.release_id),
                      decision: "reject",
                    })
                  }
                >
                  Reject
                </Button>
              </div>
            </li>
          ))}
          {!awaiting.length ? (
            <li className="text-[var(--fg-muted)]">
              No releases awaiting approval. Advance a release to the human
              gate first.
            </li>
          ) : null}
        </ul>
      </OpsPanel>
      <OpsPanel title="Approval history">
        <ul className="space-y-2">
          {history.map((a) => (
            <li
              key={str(a.approval_id)}
              className="border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <Badge tone="neutral">{str(a.decision)}</Badge>{" "}
              {str(a.approver)} · {str(a.version)} · {str(a.recorded_at)}
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IrdpRollbacksWorkspace() {
  const q = useIrdpDashboard();
  const qc = useQueryClient();
  const releases = asList(asRecord(q.data).releases).map(asRecord);
  const rollbacks = asList(asRecord(q.data).rollbacks).map(asRecord);
  const [requestedBy, setRequestedBy] = useState("release-officer");
  const plan = useMutation({
    mutationFn: (id: string) =>
      irdpApi.rollbackPlan(id, {
        requested_by: requestedBy,
        reason: "Controlled rollback plan request",
      }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["irdp"] }),
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

  return (
    <div className="space-y-4">
      <IrdpNav />
      <OpsPanel title="Rollback explorer">
        <p className="mb-3 text-[11px] text-[var(--fg-subtle)]">
          Plans only — IRDP never executes rollbacks automatically.
        </p>
        <input
          aria-label="Requested by"
          className="mb-3 w-full border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px] sm:w-72"
          value={requestedBy}
          onChange={(e) => setRequestedBy(e.target.value)}
        />
        <ul className="mb-4 space-y-2">
          {releases.slice(0, 5).map((r) => (
            <li
              key={str(r.release_id)}
              className="flex flex-wrap items-center gap-2 border border-[var(--border)]/60 px-3 py-2 text-[12px]"
            >
              <span>{str(r.version)}</span>
              <Button
                size="sm"
                variant="outline"
                disabled={plan.isPending || !requestedBy.trim()}
                onClick={() => plan.mutate(str(r.release_id))}
              >
                Generate rollback plan
              </Button>
            </li>
          ))}
        </ul>
        <ul className="space-y-2">
          {rollbacks.map((r) => (
            <li
              key={str(r.rollback_id)}
              className="border border-[var(--border)] px-3 py-2 text-[12px]"
            >
              <Badge tone="warning">plan</Badge> {str(r.version)} ·{" "}
              {str(r.requested_by)}
              <pre className="mt-2 max-h-32 overflow-auto text-[11px] text-[var(--fg-muted)]">
                {JSON.stringify(r.steps || r, null, 2)}
              </pre>
            </li>
          ))}
        </ul>
      </OpsPanel>
    </div>
  );
}

export function IrdpReportsWorkspace() {
  const q = useQuery({
    queryKey: ["irdp", "reports"],
    queryFn: () => irdpApi.reports(20),
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
      <IrdpNav />
      <OpsPanel title="Release reports">
        <ul className="space-y-2">
          {rows.map((r) => (
            <li
              key={str(r.report_id)}
              className="border border-[var(--border)] px-3 py-2 text-[12px]"
            >
              <Badge tone="neutral">{str(r.kind)}</Badge>{" "}
              <span>{str(r.title)}</span>
              <pre className="mt-2 max-h-40 overflow-auto text-[11px] text-[var(--fg-muted)]">
                {JSON.stringify(
                  r.monitoring || r.approvals || r.latest || r,
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
