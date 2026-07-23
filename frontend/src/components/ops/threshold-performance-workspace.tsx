"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { MetricCard, OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { thresholdPerformanceApi } from "@/lib/api/endpoints";
import {
  buildTpaModel,
  exportTpaCsv,
  exportTpaJson,
  exportTpaPdf,
  fmtTpa,
} from "@/lib/threshold-performance-analysis";
import { cn } from "@/lib/utils";

function HeatCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn" | "bad" | "neutral";
}) {
  return (
    <div className="border border-[var(--border)] bg-[var(--bg)]/40 px-2 py-1.5">
      <p className="text-[9px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p
        className={cn(
          "font-mono text-[11px]",
          tone === "ok" && "text-[var(--success)]",
          tone === "warn" && "text-[var(--warning)]",
          tone === "bad" && "text-[var(--danger)]",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function ThresholdPerformanceWorkspace() {
  const qc = useQueryClient();
  const reportQ = useQuery({
    queryKey: ["threshold-performance-report"],
    queryFn: thresholdPerformanceApi.report,
    retry: false,
    refetchInterval: 30_000,
  });
  const runM = useMutation({
    mutationFn: () =>
      thresholdPerformanceApi.run({ days: 90, max_evaluations: 120 }),
    onSuccess: (data) => {
      qc.setQueryData(["threshold-performance-report"], data);
    },
  });

  if (reportQ.isLoading) return <DeskSkeleton rows={8} />;
  if (reportQ.isError) {
    return (
      <DeskError
        message={
          reportQ.error instanceof Error
            ? reportQ.error.message
            : "Threshold performance unavailable"
        }
        onRetry={() => void reportQ.refetch()}
      />
    );
  }

  const model = buildTpaModel(reportQ.data);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">OFFLINE RESEARCH</Badge>
        <Badge tone="warning">LIVE THRESHOLDS UNCHANGED</Badge>
        <Button
          size="sm"
          variant="secondary"
          disabled={runM.isPending}
          onClick={() => runM.mutate()}
        >
          {runM.isPending ? "Running 90d matrix…" : "Run 90d Analysis"}
        </Button>
        {!model.empty && (
          <>
            <Button size="sm" variant="outline" onClick={() => exportTpaJson(model)}>
              Export JSON
            </Button>
            <Button size="sm" variant="outline" onClick={() => exportTpaCsv(model)}>
              Export CSV
            </Button>
            <Button size="sm" variant="outline" onClick={() => exportTpaPdf(model)}>
              Export PDF
            </Button>
          </>
        )}
      </div>

      {runM.isError && (
        <DeskError
          message={
            runM.error instanceof Error
              ? runM.error.message
              : "Analysis run failed"
          }
        />
      )}

      {model.empty ? (
        <DeskEmpty
          icon={BarChart3}
          title="No threshold performance report yet"
          description="Run the offline 90-day XAUUSD gate matrix (Q×C = 80/75/70/65/60). Research only — never lowers production thresholds."
        />
      ) : (
        <>
          <OpsPanel title="Recommendation">
            <p className="text-[13px] leading-relaxed text-[var(--fg)]">
              {model.recommendationSummary}
            </p>
            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <MetricCard label="Evaluations" value={String(model.evaluations)} />
              <MetricCard label="Generated" value={model.generatedAt.slice(0, 19)} />
              <MetricCard
                label="Action"
                value={model.recommendationAction}
                tone={
                  model.recommendationAction.includes("keep")
                    ? "ok"
                    : "warn"
                }
              />
            </div>
          </OpsPanel>

          <OpsPanel title="Rankings">
            <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
              {Object.entries(model.rankings).map(([title, rows]) => (
                <div
                  key={title}
                  className="border border-[var(--border)] bg-[var(--bg)]/30 p-3"
                >
                  <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    {title}
                  </p>
                  {rows.length === 0 ? (
                    <p className="text-[12px] text-[var(--fg-muted)]">—</p>
                  ) : (
                    <ul className="space-y-1 font-mono text-[12px]">
                      {rows.map((r) => (
                        <li
                          key={`${title}-${r.label}`}
                          className="flex justify-between gap-2"
                        >
                          <span>{r.label}</span>
                          <span>{r.value}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </OpsPanel>

          <OpsPanel title="Sensitivity Heatmap (PF · WR · Exp · DD)">
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {model.heatmap.map((h) => (
                <div
                  key={`h-${h.qualityGate}-${h.confluenceGate}`}
                  className="border border-[var(--border)] p-2"
                >
                  <p className="mb-1 text-[10px] uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                    Q{h.qualityGate} · C{h.confluenceGate}
                  </p>
                  <div className="grid grid-cols-2 gap-1">
                    <HeatCell label="PF" value={fmtTpa(h.profitFactor)} />
                    <HeatCell label="WR" value={fmtTpa(h.winRate, 3)} />
                    <HeatCell label="Exp" value={fmtTpa(h.expectancy, 3)} />
                    <HeatCell label="DD" value={fmtTpa(h.drawdown)} tone="warn" />
                  </div>
                </div>
              ))}
            </div>
          </OpsPanel>

          <OpsPanel title="Full Matrix">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1100px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                    {[
                      "Q",
                      "C",
                      "Signals",
                      "Exec",
                      "Rej",
                      "WR",
                      "LR",
                      "RR",
                      "Hold s",
                      "PF",
                      "Gross+",
                      "Gross-",
                      "Net",
                      "Exp",
                      "DD%",
                      "Rec",
                      "Sharpe",
                      "Spread",
                      "Slip",
                    ].map((h) => (
                      <th key={h} className="px-2 py-2 font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {model.matrix.map((m) => (
                    <tr
                      key={`${m.qualityGate}-${m.confluenceGate}`}
                      className={cn(
                        "border-b border-[var(--border)]/50 font-mono text-[11px]",
                        m.isBaseline && "bg-[var(--surface-2)]",
                      )}
                    >
                      <td className="px-2 py-1.5">{m.qualityGate}</td>
                      <td className="px-2 py-1.5">{m.confluenceGate}</td>
                      <td className="px-2 py-1.5">{m.totalSignals}</td>
                      <td className="px-2 py-1.5">{m.executedTrades}</td>
                      <td className="px-2 py-1.5">{m.rejectedTrades}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.winRate, 3)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.lossRate, 3)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.averageRr)}</td>
                      <td className="px-2 py-1.5">
                        {fmtTpa(m.averageHoldingTimeSec, 0)}
                      </td>
                      <td className="px-2 py-1.5">{fmtTpa(m.profitFactor)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.grossProfit)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.grossLoss)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.netProfit)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.expectancy, 3)}</td>
                      <td className="px-2 py-1.5">
                        {fmtTpa(m.maximumDrawdownPct)}
                      </td>
                      <td className="px-2 py-1.5">{fmtTpa(m.recoveryFactor)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.sharpeRatio)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.averageSpread)}</td>
                      <td className="px-2 py-1.5">{fmtTpa(m.averageSlippage)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </OpsPanel>
        </>
      )}
    </div>
  );
}
