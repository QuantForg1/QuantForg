"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ArrowUpFromLine } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, bool, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function fmt(v: unknown, d = 4): string {
  const n = num(v, NaN);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(d);
}

export function ThresholdPromotionWorkspace() {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const [confirmPromote, setConfirmPromote] = useState(false);
  const [confirmRollback, setConfirmRollback] = useState(false);

  const statusQ = useQuery({
    queryKey: ["ite-ops-threshold-promotion"],
    queryFn: iteOpsApi.thresholdPromotion,
    retry: false,
    refetchInterval: 12_000,
  });

  const promoteM = useMutation({
    mutationFn: () =>
      iteOpsApi.thresholdPromote({
        reason: reason.trim() || "operator_promote_q70_c75",
        confirmed: true,
        evidence_reference: "candidate_validation_latest.json",
      }),
    onSuccess: () => {
      setConfirmPromote(false);
      void qc.invalidateQueries({ queryKey: ["ite-ops-threshold-promotion"] });
    },
  });

  const rollbackM = useMutation({
    mutationFn: () =>
      iteOpsApi.thresholdRollback({
        reason: reason.trim() || "operator_rollback_to_80_80",
        confirmed: true,
      }),
    onSuccess: () => {
      setConfirmRollback(false);
      void qc.invalidateQueries({ queryKey: ["ite-ops-threshold-promotion"] });
    },
  });

  if (statusQ.isLoading) return <DeskSkeleton rows={8} />;
  if (statusQ.isError) {
    return (
      <DeskError
        message={
          statusQ.error instanceof Error
            ? statusQ.error.message
            : "Threshold promotion unavailable"
        }
        onRetry={() => void statusQ.refetch()}
      />
    );
  }

  const root = asRecord(statusQ.data);
  const production = asRecord(root.production);
  const candidate = asRecord(root.candidate);
  const rollback = asRecord(root.rollback_point);
  const evidence = asRecord(root.research_evidence);
  const decision = asRecord(evidence.decision);
  const monitoring = asRecord(root.monitoring);
  const live = asRecord(monitoring.live);
  const promoted = bool(root.promoted);
  const comparison = asList(evidence.comparison);
  const experimentalBadge = str(root.experimental_badge, "");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">OPERATOR GATED</Badge>
        <Badge tone="warning">NEVER AUTO-PROMOTE</Badge>
        <Badge tone="warning">NEVER AUTO-ROLLBACK</Badge>
        {experimentalBadge ? (
          <Badge tone="warning">{experimentalBadge}</Badge>
        ) : null}
      </div>

      {experimentalBadge ? (
        <div
          className="border border-[var(--warning)]/40 bg-[var(--warning)]/10 px-3 py-2 text-[13px] text-[var(--warning)]"
          role="status"
        >
          {experimentalBadge} — manage at{" "}
          <a
            className="underline"
            href="/experimental-threshold"
          >
            Experimental Threshold
          </a>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <OpsPanel title="Current Production">
          <div className="grid gap-2">
            <MetricCard
              label="Quality"
              value={str(production.quality, "80")}
              large
              tone="ok"
            />
            <MetricCard
              label="Confluence"
              value={str(production.confluence, "80")}
              large
              tone="ok"
            />
            <p className="font-mono text-[11px] text-[var(--fg-subtle)]">
              {str(production.config_version)}
            </p>
          </div>
        </OpsPanel>
        <OpsPanel title="Candidate">
          <div className="grid gap-2">
            <MetricCard
              label="Quality"
              value={str(candidate.quality, "70")}
              large
            />
            <MetricCard
              label="Confluence"
              value={str(candidate.confluence, "75")}
              large
            />
            <p className="text-[12px] text-[var(--fg-muted)]">
              Requires explicit operator approval to apply.
            </p>
          </div>
        </OpsPanel>
        <OpsPanel title="Rollback Point">
          <div className="grid gap-2">
            <MetricCard
              label="Quality / Confluence"
              value={`${str(rollback.quality, "80")} / ${str(rollback.confluence, "80")}`}
              large
              tone="ok"
            />
            <Button
              size="sm"
              variant="outline"
              disabled={rollbackM.isPending || !promoted}
              onClick={() => setConfirmRollback(true)}
            >
              Single-click rollback to 80 / 80
            </Button>
          </div>
        </OpsPanel>
      </div>

      <OpsPanel title="Research Evidence · Candidate Validation Report">
        {str(evidence.status) !== "available" ? (
          <DeskEmpty
            icon={ArrowUpFromLine}
            title="No candidate validation evidence on disk"
            description="Run Research → Candidate Validation first. Promotion still requires explicit confirmation."
          />
        ) : (
          <>
            <p className="mb-3 text-[13px] text-[var(--fg)]">
              {str(
                decision.summary,
                "Review comparison metrics before any promotion.",
              )}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[560px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    <th className="px-2 py-2">Metric</th>
                    <th className="px-2 py-2">Production 80/80</th>
                    <th className="px-2 py-2">Candidate 70/75</th>
                    <th className="px-2 py-2">Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.map((raw) => {
                    const r = asRecord(raw);
                    return (
                      <tr
                        key={str(r.key)}
                        className="border-b border-[var(--border)]/50 font-mono text-[12px]"
                      >
                        <td className="px-2 py-1.5">{str(r.metric)}</td>
                        <td className="px-2 py-1.5">{fmt(r.production)}</td>
                        <td className="px-2 py-1.5">{fmt(r.candidate)}</td>
                        <td className="px-2 py-1.5">{fmt(r.delta)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </OpsPanel>

      <OpsPanel title="Promotion Workflow">
        <ol className="mb-3 list-decimal space-y-1 pl-5 text-[12px] text-[var(--fg-muted)]">
          {asList(root.workflow_steps).map((s) => (
            <li key={String(s)}>{String(s)}</li>
          ))}
        </ol>
        <label className="mb-2 block text-[11px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
          Reason
        </label>
        <textarea
          className="mb-3 w-full border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-[12px] text-[var(--fg)]"
          rows={2}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Operator reason for promote or rollback…"
        />
        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={promoteM.isPending || promoted}
            onClick={() => setConfirmPromote(true)}
          >
            {promoted ? "Already promoted" : "Approve promotion → Q70 / C75"}
          </Button>
        </div>
        {promoteM.isError && (
          <p className="mt-2 text-[12px] text-[var(--danger)]">
            {promoteM.error instanceof Error
              ? promoteM.error.message
              : "Promote failed"}
          </p>
        )}
        {rollbackM.isError && (
          <p className="mt-2 text-[12px] text-[var(--danger)]">
            {rollbackM.error instanceof Error
              ? rollbackM.error.message
              : "Rollback failed"}
          </p>
        )}
      </OpsPanel>

      {confirmPromote && (
        <OpsPanel title="Confirm promotion">
          <p className="mb-3 text-[13px]">
            Apply Quality=70 / Confluence=75 now? This creates a rollback point
            at 80/80 and does not restart the engine. DEFAULT_ITE_CONFIG stays
            80/80.
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => promoteM.mutate()}
              disabled={promoteM.isPending}
            >
              Confirm promote
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setConfirmPromote(false)}
            >
              Cancel
            </Button>
          </div>
        </OpsPanel>
      )}

      {confirmRollback && (
        <OpsPanel title="Confirm rollback">
          <p className="mb-3 text-[13px]">
            Restore Quality=80 / Confluence=80 and record audit trail?
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => rollbackM.mutate()}
              disabled={rollbackM.isPending}
            >
              Confirm rollback
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setConfirmRollback(false)}
            >
              Cancel
            </Button>
          </div>
        </OpsPanel>
      )}

      <OpsPanel title="Post-promotion monitoring (next 500 cycles)">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Cycles observed"
            value={str(live.cycles_observed, "0")}
          />
          <MetricCard
            label="Execution rate"
            value={
              live.execution_rate_pct == null
                ? "—"
                : `${fmt(live.execution_rate_pct, 1)}%`
            }
          />
          <MetricCard label="Win rate" value={fmt(live.win_rate, 3)} />
          <MetricCard label="Profit factor" value={fmt(live.profit_factor)} />
          <MetricCard label="Expectancy" value={fmt(live.expectancy, 3)} />
          <MetricCard label="Drawdown" value={fmt(live.drawdown_pct)} />
          <MetricCard label="Average RR" value={fmt(live.average_rr)} />
          <MetricCard
            label="Avg latency ms"
            value={fmt(live.average_latency_ms, 1)}
          />
        </div>
        <p className="mt-3 text-[12px] text-[var(--fg-muted)]">
          Material degradation raises a warning only — never auto-rollback.
        </p>
        <div className="mt-2 space-y-2">
          {asList(monitoring.warnings).map((w) => {
            const r = asRecord(w);
            return (
              <div
                key={str(r.utc_timestamp)}
                className={cn(
                  "border border-[var(--warning)] bg-[var(--warning-soft)] px-3 py-2 text-[12px]",
                )}
              >
                {str(r.message)}
              </div>
            );
          })}
        </div>
      </OpsPanel>

      <OpsPanel title="Audit trail">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                <th className="px-2 py-2">UTC</th>
                <th className="px-2 py-2">Action</th>
                <th className="px-2 py-2">Operator</th>
                <th className="px-2 py-2">From</th>
                <th className="px-2 py-2">To</th>
                <th className="px-2 py-2">Reason</th>
                <th className="px-2 py-2">Commit</th>
              </tr>
            </thead>
            <tbody>
              {asList(root.audit_trail).map((raw) => {
                const r = asRecord(raw);
                const prev = asRecord(r.previous_thresholds);
                const next = asRecord(r.new_thresholds);
                return (
                  <tr
                    key={str(r.id)}
                    className="border-b border-[var(--border)]/50 font-mono text-[11px]"
                  >
                    <td className="px-2 py-1.5">
                      {str(r.utc_timestamp).slice(0, 19)}
                    </td>
                    <td className="px-2 py-1.5">{str(r.action)}</td>
                    <td className="px-2 py-1.5">{str(r.operator)}</td>
                    <td className="px-2 py-1.5">
                      {str(prev.quality)}/{str(prev.confluence)}
                    </td>
                    <td className="px-2 py-1.5">
                      {str(next.quality)}/{str(next.confluence)}
                    </td>
                    <td className="max-w-[180px] truncate px-2 py-1.5">
                      {str(r.reason)}
                    </td>
                    <td className="max-w-[100px] truncate px-2 py-1.5">
                      {str(r.commit_hash, "—").slice(0, 10)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </OpsPanel>
    </div>
  );
}
