"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { qptcmApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/quantforg-paper-trading", label: "Dashboard" },
  { href: "/quantforg-paper-trading/explorer", label: "Explorer" },
  { href: "/quantforg-paper-trading/timeline", label: "Timeline" },
  { href: "/quantforg-paper-trading/evidence", label: "Evidence" },
  { href: "/quantforg-paper-trading/graduation", label: "Graduation" },
  { href: "/quantforg-paper-trading/reports", label: "Reports" },
] as const;

export function QptcmNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/quantforg-paper-trading"
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
      <Badge tone="neutral">PAPER TRADING</Badge>
      <Badge tone="success">NO LIVE TRADES</Badge>
      <Badge tone="warning">HUMAN-GATED GRADUATION</Badge>
      <Badge tone="neutral">NO CAPITAL ALLOCATION</Badge>
    </div>
  );
}

export function QptcmDashboardWorkspace() {
  const q = useQuery({
    queryKey: ["qptcm", "dashboard"],
    queryFn: () => qptcmApi.dashboard(),
    refetchInterval: 60_000,
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "QPTCM unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const root = asRecord(q.data);
  const dash = asRecord(asRecord(root.sections).campaign_dashboard);
  const counts = asRecord(dash.lifecycle_counts);

  return (
    <div className="space-y-4">
      <QptcmNav />
      <IsolationBadges />
      <p className="text-[11px] text-[var(--fg-subtle)]">
        Governed paper-trading campaigns for certified strategies. Never places
        live trades or auto-approves graduation.
      </p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Campaigns"
          value={str(dash.campaign_count, "—")}
        />
        <MetricCard label="Running" value={str(counts.Running, "0")} />
        <MetricCard label="Reviewed" value={str(counts.Reviewed, "0")} />
        <MetricCard
          label="Grad candidates"
          value={str(dash.graduation_candidates, "0")}
        />
      </div>
      <OpsPanel title="Lifecycle counts">
        <div className="flex flex-wrap gap-2">
          {Object.entries(counts).map(([k, v]) => (
            <span
              key={k}
              className="border border-[var(--border)] px-2 py-1 font-mono text-[10px] text-[var(--fg-muted)]"
            >
              {k}: {str(v)}
            </span>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QptcmExplorerWorkspace() {
  const q = useQuery({
    queryKey: ["qptcm", "campaigns"],
    queryFn: () => qptcmApi.campaigns(),
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error ? q.error.message : "Campaigns unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }
  const campaigns = asList(asRecord(q.data).campaigns).map(asRecord);

  return (
    <div className="space-y-4">
      <QptcmNav />
      <IsolationBadges />
      <OpsPanel title="Campaign Explorer">
        <div className="max-h-[520px] space-y-2 overflow-y-auto">
          {campaigns.map((c) => (
            <div
              key={str(c.campaign_id)}
              className="border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="neutral">{str(c.lifecycle)}</Badge>
                <span className="text-[13px] text-[var(--fg)]">
                  {str(c.strategy_name)}
                </span>
              </div>
              <div className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                {str(c.campaign_id)} · {str(c.market)} · next{" "}
                {str(c.next_lifecycle, "—")}
              </div>
              <div className="mt-1 text-[11px] text-[var(--fg-muted)]">
                window {str(asRecord(c.time_window).start)} →{" "}
                {str(asRecord(c.time_window).end)}
              </div>
            </div>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QptcmTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["qptcm", "timeline"],
    queryFn: () => qptcmApi.timeline(),
  });
  if (q.isLoading) return <DeskSkeleton rows={8} />;
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
  const events = asList(asRecord(q.data).daily_timeline).map(asRecord);

  return (
    <div className="space-y-4">
      <QptcmNav />
      <IsolationBadges />
      <OpsPanel title="Daily Timeline">
        <ol className="relative max-h-[520px] space-y-2 overflow-y-auto border-l border-[var(--border)] pl-4">
          {events.map((e, i) => (
            <li key={`${str(e.snapshot_id || e.date)}-${i}`} className="relative">
              <span className="absolute -left-[21px] top-1 h-2 w-2 rounded-full bg-[var(--fg-muted)]" />
              <div className="font-mono text-[11px] text-[var(--fg)]">
                {str(e.date)} · {str(e.strategy_id)} · pnl {str(e.paper_pnl)}
              </div>
              <div className="text-[10px] text-[var(--fg-muted)]">
                fills {str(e.fills)} · incidents {str(e.incidents)} · paper only
              </div>
            </li>
          ))}
          {events.length === 0 ? (
            <li className="text-[12px] text-[var(--fg-muted)]">No snapshots.</li>
          ) : null}
        </ol>
      </OpsPanel>
    </div>
  );
}

export function QptcmEvidenceWorkspace() {
  const q = useQuery({
    queryKey: ["qptcm", "evidence"],
    queryFn: () => qptcmApi.evidence(),
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
  const rows = asList(
    asRecord(asRecord(q.data).evidence_center).campaigns,
  ).map(asRecord);

  return (
    <div className="space-y-4">
      <QptcmNav />
      <IsolationBadges />
      <OpsPanel title="Evidence Center">
        <div className="max-h-[520px] space-y-3 overflow-y-auto">
          {rows.map((r) => (
            <div
              key={str(r.campaign_id)}
              className="border border-[var(--border)] px-3 py-2"
            >
              <div className="font-mono text-[11px] text-[var(--fg)]">
                {str(r.campaign_id)}
              </div>
              <div className="mt-1 text-[11px] text-[var(--fg-muted)]">
                evidence:{" "}
                {asList(r.evidence)
                  .map((e) => str(asRecord(e).source))
                  .join(", ")}
              </div>
              <div className="mt-1 text-[11px] text-[var(--fg-muted)]">
                recs:{" "}
                {asList(r.recommendations)
                  .map((x) => str(x))
                  .join(" · ")}
              </div>
            </div>
          ))}
        </div>
      </OpsPanel>
    </div>
  );
}

export function QptcmGraduationWorkspace() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);
  const grad = useQuery({
    queryKey: ["qptcm", "graduation"],
    queryFn: () => qptcmApi.graduation(),
  });
  const approvals = useQuery({
    queryKey: ["qptcm", "approvals"],
    queryFn: () => qptcmApi.approvals(),
  });
  const mutate = useMutation({
    mutationFn: qptcmApi.approve,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["qptcm"] });
      setBusy(null);
    },
    onError: () => setBusy(null),
  });

  if (grad.isLoading) return <DeskSkeleton rows={8} />;
  if (grad.isError) {
    return (
      <DeskError
        message={
          grad.error instanceof Error
            ? grad.error.message
            : "Graduation unavailable"
        }
        onRetry={() => void grad.refetch()}
      />
    );
  }

  const workspace = asRecord(asRecord(grad.data).graduation_workspace);
  const candidates = asList(workspace.candidates).map(asRecord);
  const queue = asList(asRecord(approvals.data).queue).map(asRecord);

  return (
    <div className="space-y-4">
      <QptcmNav />
      <IsolationBadges />
      <OpsPanel title="Graduation Workspace">
        <p className="mb-3 text-[11px] text-[var(--fg-subtle)]">
          {str(workspace.note)}
        </p>
        <div className="max-h-[240px] space-y-2 overflow-y-auto">
          {candidates.length === 0 ? (
            <p className="text-[12px] text-[var(--fg-muted)]">
              No graduation-stage campaigns yet.
            </p>
          ) : (
            candidates.map((c) => (
              <div
                key={str(c.campaign_id)}
                className="border border-[var(--border)] px-3 py-2"
              >
                <div className="text-[13px] text-[var(--fg)]">
                  {str(c.strategy_name)}
                </div>
                <div className="text-[11px] text-[var(--fg-muted)]">
                  {str(c.lifecycle)} · live blocked
                </div>
              </div>
            ))
          )}
        </div>
      </OpsPanel>
      <OpsPanel title="Lifecycle approval queue">
        <div className="max-h-[280px] space-y-2 overflow-y-auto">
          {queue.map((item) => (
            <div
              key={str(item.campaign_id)}
              className="border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2"
            >
              <div className="text-[12px] text-[var(--fg)]">
                {str(item.strategy_name)} · {str(item.from_state)} →{" "}
                {str(item.to_state)}
              </div>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  disabled={busy === str(item.campaign_id) || !item.to_state}
                  className="border border-[var(--border-strong)] px-2 py-1 text-[11px] uppercase tracking-[0.08em]"
                  onClick={() => {
                    setBusy(str(item.campaign_id));
                    mutate.mutate({
                      campaign_id: str(item.campaign_id),
                      to_state: str(item.to_state),
                      decision: "approved",
                    });
                  }}
                >
                  Approve
                </button>
                <button
                  type="button"
                  disabled={busy === str(item.campaign_id) || !item.to_state}
                  className="border border-[var(--border)] px-2 py-1 text-[11px] uppercase tracking-[0.08em] text-[var(--fg-muted)]"
                  onClick={() => {
                    setBusy(str(item.campaign_id));
                    mutate.mutate({
                      campaign_id: str(item.campaign_id),
                      to_state: str(item.to_state),
                      decision: "rejected",
                    });
                  }}
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
        {mutate.isError ? (
          <p className="mt-2 text-[11px] text-[var(--danger)]">
            {mutate.error instanceof Error
              ? mutate.error.message
              : "Approval failed"}
          </p>
        ) : null}
      </OpsPanel>
    </div>
  );
}

export function QptcmReportsWorkspace() {
  const q = useQuery({
    queryKey: ["qptcm", "reports"],
    queryFn: () => qptcmApi.reports(20),
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
      <QptcmNav />
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
        </div>
      </OpsPanel>
    </div>
  );
}
