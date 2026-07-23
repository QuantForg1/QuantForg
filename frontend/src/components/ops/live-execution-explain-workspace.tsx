"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, MessageSquareWarning } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, bool, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

type Stage = {
  key: string;
  label: string;
  status: string;
  detail: string;
  blocking: boolean;
};

function parseStages(raw: unknown): Stage[] {
  return asList(raw).map((row) => {
    const r = asRecord(row);
    return {
      key: str(r.key),
      label: str(r.label),
      status: str(r.status),
      detail: str(r.detail),
      blocking: bool(r.blocking),
    };
  });
}

function DecisionCard({
  explain,
  meta,
}: {
  explain: Record<string, unknown>;
  meta?: { recordedAt?: string; signalId?: string };
}) {
  const [open, setOpen] = useState(false);
  const execute = bool(explain.execute_trade);
  const headline = str(explain.headline, execute ? "✅ EXECUTE TRADE" : "❌ NO TRADE");
  const reasons = asList(explain.reasons).map((r) => str(r));
  const primary = str(explain.primary_rejection_detail || explain.primary_rejection, "");
  const stages = parseStages(explain.stages);

  return (
    <article
      className={cn(
        "border px-3 py-3",
        execute
          ? "border-[var(--success)]/35 bg-[var(--success)]/5"
          : "border-[var(--danger)]/35 bg-[var(--danger)]/5",
      )}
    >
      <header className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <div>
          <p
            className={cn(
              "text-[15px] font-semibold tracking-tight",
              execute ? "text-[var(--success)]" : "text-[var(--danger)]",
            )}
          >
            {headline}
          </p>
          <p className="mt-0.5 font-mono text-[11px] tabular-nums text-[var(--fg-subtle)]">
            {meta?.recordedAt ? str(meta.recordedAt) : str(explain.recorded_at)}
            {meta?.signalId || explain.signal_id
              ? ` · ${str(meta?.signalId || explain.signal_id).slice(0, 12)}`
              : ""}
            {explain.decision_action
              ? ` · ${str(explain.decision_action)}`
              : ""}
          </p>
        </div>
        <Badge tone={execute ? "success" : "danger"}>
          {execute ? "EXECUTE_TRADE" : "NO_TRADE"}
        </Badge>
      </header>

      {execute ? (
        <div>
          <p className="mb-1 text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Reason
          </p>
          <ul className="space-y-1">
            {reasons.map((line) => (
              <li
                key={line}
                className="font-mono text-[12px] text-[var(--success)]"
              >
                - {line}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div>
          <p className="mb-1 text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Primary rejection
          </p>
          <p className="font-mono text-[13px] font-semibold text-[var(--danger)]">
            {primary || "NO TRADE"}
          </p>
        </div>
      )}

      <div className="mt-3">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setOpen((v) => !v)}
          className="gap-1"
        >
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
          View Full Decision Trace
        </Button>
        {open ? (
          <ol className="mt-3 space-y-2 border-t border-[var(--border)] pt-3">
            {stages.map((stage, idx) => (
              <li
                key={`${stage.key}-${idx}`}
                className="grid grid-cols-[28px_1fr] gap-2"
              >
                <span className="font-mono text-[11px] text-[var(--fg-subtle)]">
                  {idx + 1}.
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[12px] font-semibold text-[var(--fg)]">
                      {stage.label}
                    </span>
                    <span
                      className={cn(
                        "font-mono text-[11px]",
                        stage.status === "PASS" && "text-[var(--success)]",
                        stage.status === "FAIL" && "text-[var(--danger)]",
                        stage.status === "SKIP" && "text-[var(--fg-subtle)]",
                      )}
                    >
                      {stage.status}
                      {stage.blocking ? " · BLOCKING" : ""}
                    </span>
                  </div>
                  <p className="font-mono text-[12px] text-[var(--fg-muted)]">
                    {stage.detail}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        ) : null}
      </div>
    </article>
  );
}

export function LiveExecutionExplainWorkspace() {
  const q = useQuery({
    queryKey: ["ite-ops-live-execution-explain"],
    queryFn: () => iteOpsApi.liveExecutionExplain(40),
    retry: false,
    refetchInterval: 8_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={6} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Live Execution Explain unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const evaluations = asList(root.evaluations).map(asRecord);
  const latest = asRecord(root.latest);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">EXPLAIN MODE</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">ENGINES UNCHANGED</Badge>
      </div>

      <OpsPanel title="Latest evaluation">
        {latest.verdict ? (
          <DecisionCard explain={latest} />
        ) : (
          <DeskEmpty
            icon={MessageSquareWarning}
            title="No live evaluations yet"
            description="Decision cards appear for every live ITE evaluation recorded by Strategy Diagnostics."
          />
        )}
      </OpsPanel>

      {evaluations.length > 0 ? (
        <OpsPanel title={`Recent evaluations (${evaluations.length})`}>
          <div className="space-y-3">
            {evaluations.map((row, i) => {
              const explain = asRecord(row.explain);
              return (
                <DecisionCard
                  key={`${str(row.signal_id, String(i))}-${str(row.recorded_at)}`}
                  explain={explain}
                  meta={{
                    recordedAt: str(row.recorded_at),
                    signalId: str(row.signal_id),
                  }}
                />
              );
            })}
          </div>
        </OpsPanel>
      ) : null}
    </div>
  );
}
