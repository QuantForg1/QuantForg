"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCompare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { candidateValidationApi } from "@/lib/api/endpoints";
import { asList, asRecord, bool, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

function fmt(v: unknown, d = 4): string {
  const n = num(v, NaN);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(d);
}

export function CandidateValidationWorkspace() {
  const qc = useQueryClient();
  const reportQ = useQuery({
    queryKey: ["candidate-validation-report"],
    queryFn: candidateValidationApi.report,
    retry: false,
  });
  const runM = useMutation({
    mutationFn: () =>
      candidateValidationApi.run({ days: 90, max_evaluations: 120 }),
    onSuccess: (data) => {
      qc.setQueryData(["candidate-validation-report"], data);
    },
  });

  if (reportQ.isLoading) return <DeskSkeleton rows={6} />;
  if (reportQ.isError) {
    return (
      <DeskError
        message={
          reportQ.error instanceof Error
            ? reportQ.error.message
            : "Candidate validation unavailable"
        }
        onRetry={() => void reportQ.refetch()}
      />
    );
  }

  const root = asRecord(reportQ.data);
  const empty = str(root.status) === "empty" || !asList(root.comparison).length;
  const decision = asRecord(root.decision);
  const recommend = bool(decision.recommend_candidate);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">OFFLINE RESEARCH</Badge>
        <Badge tone="warning">PRODUCTION UNCHANGED</Badge>
        <Button
          size="sm"
          variant="secondary"
          disabled={runM.isPending}
          onClick={() => runM.mutate()}
        >
          {runM.isPending ? "Validating…" : "Run 90d A/B Validation"}
        </Button>
      </div>

      {empty ? (
        <DeskEmpty
          icon={GitCompare}
          title="No candidate validation yet"
          description="Compare production Q80/C80 vs candidate Q70/C75 on the same 90-day XAUUSD walk. Never modifies production."
        />
      ) : (
        <>
          <OpsPanel title="Decision">
            <p
              className={cn(
                "text-[13px] leading-relaxed",
                recommend ? "text-[var(--warning)]" : "text-[var(--success)]",
              )}
            >
              {str(decision.summary, "Recommend keeping 80 / 80.")}
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <MetricCard label="Production" value="Q80 / C80" tone="ok" />
              <MetricCard label="Candidate" value="Q70 / C75" />
              <MetricCard
                label="Recommend candidate"
                value={recommend ? "ELIGIBLE (not applied)" : "NO — KEEP 80/80"}
                tone={recommend ? "warn" : "ok"}
              />
            </div>
          </OpsPanel>

          <OpsPanel title="Comparison">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    <th className="px-2 py-2">Metric</th>
                    <th className="px-2 py-2">Production 80/80</th>
                    <th className="px-2 py-2">Candidate 70/75</th>
                    <th className="px-2 py-2">Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {asList(root.comparison).map((raw) => {
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
          </OpsPanel>
        </>
      )}
    </div>
  );
}
