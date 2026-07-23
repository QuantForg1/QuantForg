"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { FlaskConical } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, bool, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function fmt(v: unknown, d = 4): string {
  const n = num(v, NaN);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(d);
}

export function ExperimentalThresholdWorkspace() {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const [confirmActivate, setConfirmActivate] = useState(false);
  const [confirmRollback, setConfirmRollback] = useState(false);

  const statusQ = useQuery({
    queryKey: ["ite-ops-experimental-threshold"],
    queryFn: iteOpsApi.experimentalThreshold,
    retry: false,
    refetchInterval: 10_000,
  });

  const activateM = useMutation({
    mutationFn: () =>
      iteOpsApi.experimentalActivate({
        reason: reason.trim() || "operator_activate_experimental_75_75",
        confirmed: true,
      }),
    onSuccess: () => {
      setConfirmActivate(false);
      void qc.invalidateQueries({ queryKey: ["ite-ops-experimental-threshold"] });
      void qc.invalidateQueries({ queryKey: ["ite-ops-threshold-promotion"] });
    },
  });

  const rollbackM = useMutation({
    mutationFn: () =>
      iteOpsApi.experimentalRollback({
        reason: reason.trim() || "operator_rollback_experimental_to_80_80",
        confirmed: true,
      }),
    onSuccess: () => {
      setConfirmRollback(false);
      void qc.invalidateQueries({ queryKey: ["ite-ops-experimental-threshold"] });
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
            : "Experimental threshold profile unavailable"
        }
        onRetry={() => void statusQ.refetch()}
      />
    );
  }

  const root = asRecord(statusQ.data);
  const active = bool(root.active);
  const badge = str(root.badge, "");
  const institutional = asRecord(root.institutional_default);
  const experimental = asRecord(root.experimental_gates);
  const monitoring = asRecord(root.monitoring);
  const expLive = asRecord(monitoring.experimental);
  const baseLive = asRecord(monitoring.baseline_shadow_80_80);
  const lastReport = asRecord(root.last_report);
  const recommendation = str(lastReport.recommendation, "");
  const evals = num(monitoring.evaluations, 0);
  const target = num(monitoring.eval_target, 100);
  const remaining = num(monitoring.remaining, 100);
  const audit = asList(root.audit_trail).map(asRecord);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">OPERATOR GATED</Badge>
        <Badge tone="warning">NEVER AUTO-PROMOTE</Badge>
        <Badge tone="success">DEFAULT Q80/C80 FROZEN</Badge>
        {active && badge ? (
          <Badge tone="warning">{badge}</Badge>
        ) : (
          <Badge tone="neutral">Experimental inactive</Badge>
        )}
      </div>

      {active && badge ? (
        <div
          className="border border-[var(--warning)]/40 bg-[var(--warning)]/10 px-3 py-2 text-[13px] text-[var(--warning)]"
          role="status"
        >
          {badge}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <OpsPanel title="Institutional default">
          <MetricCard
            label="Quality / Confluence"
            value={`Q${str(institutional.quality, "80")} / C${str(institutional.confluence, "80")}`}
            tone="ok"
            large
          />
          <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
            DEFAULT_ITE_CONFIG stays frozen. Experimental never mutates it.
          </p>
        </OpsPanel>
        <OpsPanel title="EXPERIMENTAL_75">
          <MetricCard
            label="Quality / Confluence"
            value={`Q${str(experimental.quality, "75")} / C${str(experimental.confluence, "75")}`}
            tone={active ? "warn" : "neutral"}
            large
          />
          <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
            Temporary overlay only. Risk / Safety / OMS / min-lot unchanged.
          </p>
        </OpsPanel>
        <OpsPanel title="100-eval monitor">
          <MetricCard
            label="Eligible evaluations"
            value={`${evals} / ${target}`}
            large
          />
          <p className="mt-2 font-mono text-[12px] tabular-nums text-[var(--fg-muted)]">
            Remaining: {remaining}
          </p>
        </OpsPanel>
      </div>

      <OpsPanel title="Operator controls">
        <label className="mb-2 block text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
          Reason (audit log)
        </label>
        <input
          className="mb-3 w-full border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-[13px] text-[var(--fg)] outline-none focus:border-[var(--fg-muted)]"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Why activate or rollback?"
        />
        <div className="flex flex-wrap items-center gap-2">
          {!active ? (
            <>
              <label className="flex items-center gap-2 text-[12px] text-[var(--fg-muted)]">
                <input
                  type="checkbox"
                  checked={confirmActivate}
                  onChange={(e) => setConfirmActivate(e.target.checked)}
                />
                Confirm activate Q75/C75
              </label>
              <Button
                size="sm"
                disabled={!confirmActivate || activateM.isPending}
                onClick={() => activateM.mutate()}
              >
                {activateM.isPending ? "Activating…" : "Activate EXPERIMENTAL_75"}
              </Button>
            </>
          ) : (
            <>
              <label className="flex items-center gap-2 text-[12px] text-[var(--fg-muted)]">
                <input
                  type="checkbox"
                  checked={confirmRollback}
                  onChange={(e) => setConfirmRollback(e.target.checked)}
                />
                Confirm rollback
              </label>
              <Button
                size="sm"
                variant="secondary"
                disabled={!confirmRollback || rollbackM.isPending}
                onClick={() => rollbackM.mutate()}
              >
                {rollbackM.isPending ? "Rolling back…" : "Rollback to Q80/C80"}
              </Button>
            </>
          )}
        </div>
        {(activateM.isError || rollbackM.isError) && (
          <p className="mt-2 text-[12px] text-[var(--danger)]">
            {(activateM.error || rollbackM.error) instanceof Error
              ? (activateM.error || rollbackM.error)?.message
              : "Action failed"}
          </p>
        )}
      </OpsPanel>

      <OpsPanel title="Live comparison (75/75 vs shadow 80/80)">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                <th className="py-2 pr-3 font-medium">Metric</th>
                <th className="py-2 pr-3 font-medium">Experimental 75/75</th>
                <th className="py-2 font-medium">Baseline 80/80</th>
              </tr>
            </thead>
            <tbody>
              {(
                [
                  ["Signals generated", "signals_generated"],
                  ["Trades executed", "trades_executed"],
                  ["Win rate", "win_rate"],
                  ["Profit factor", "profit_factor"],
                  ["Expectancy", "expectancy"],
                  ["Drawdown %", "drawdown_pct"],
                  ["Average RR", "average_rr"],
                ] as const
              ).map(([label, key]) => (
                <tr key={key} className="border-b border-[var(--border)]/60">
                  <td className="py-2 pr-3 text-[12px]">{label}</td>
                  <td className="py-2 pr-3 font-mono text-[13px] tabular-nums">
                    {fmt(expLive[key], key.includes("rate") || key === "win_rate" ? 4 : 4)}
                  </td>
                  <td className="py-2 font-mono text-[13px] tabular-nums">
                    {fmt(baseLive[key], 4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </OpsPanel>

      {recommendation ? (
        <OpsPanel title="EXPERIMENTAL_THRESHOLD_REPORT">
          <p
            className={cn(
              "text-[14px] font-semibold",
              recommendation.includes("Keep")
                ? "text-[var(--warning)]"
                : "text-[var(--success)]",
            )}
          >
            Recommendation: {recommendation}
          </p>
          <p className="mt-2 text-[12px] text-[var(--fg-muted)]">
            {str(
              asRecord(lastReport.recommendation_detail).summary,
              "Report available after 100 eligible evaluations.",
            )}
          </p>
          <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
            Never auto-promoted. Operator approval still required.
          </p>
        </OpsPanel>
      ) : (
        <OpsPanel title="EXPERIMENTAL_THRESHOLD_REPORT">
          <div className="flex items-start gap-2 text-[13px] text-[var(--fg-muted)]">
            <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />
            <p>
              Report auto-generates after {target} eligible live evaluations
              ({evals} so far). It will compare 75/75 vs 80/80 and recommend Keep
              or Revert — without promoting automatically.
            </p>
          </div>
        </OpsPanel>
      )}

      <OpsPanel title="Audit trail">
        {audit.length === 0 ? (
          <p className="text-[12px] text-[var(--fg-muted)]">No activations yet.</p>
        ) : (
          <ul className="space-y-2">
            {audit.slice(0, 12).map((row) => (
              <li
                key={str(row.id, str(row.utc_timestamp))}
                className="border-b border-[var(--border)]/60 pb-2 text-[12px]"
              >
                <span className="font-mono tabular-nums text-[var(--fg-subtle)]">
                  {str(row.utc_timestamp)}
                </span>
                {" · "}
                <span className="font-semibold">{str(row.action)}</span>
                {" · "}
                {str(row.operator)}
                {row.reason ? ` — ${str(row.reason)}` : ""}
              </li>
            ))}
          </ul>
        )}
      </OpsPanel>
    </div>
  );
}
