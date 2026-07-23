"use client";

import { useQuery } from "@tanstack/react-query";
import { LineChart } from "lucide-react";
import dynamic from "next/dynamic";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { OpsPanel } from "@/components/ops/auto-trading-ops-ui";
import { iteOpsApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

const OpportunityTrendChart = dynamic(
  () =>
    import("@/components/charts/opportunity-trend-chart").then(
      (m) => m.OpportunityTrendChart,
    ),
  { ssr: false, loading: () => <Skeleton className="h-44 w-full" /> },
);

function parseSeries(raw: unknown): { label: string; v: number; t?: string }[] {
  const out: { label: string; v: number; t?: string }[] = [];
  for (const row of asList(raw)) {
    const r = asRecord(row);
    const v = num(r.v);
    if (Number.isNaN(v)) continue;
    const t = str(r.t, "");
    out.push({ label: str(r.label, ""), v, ...(t ? { t } : {}) });
  }
  return out;
}

function meterTone(level: string): "success" | "warning" | "danger" | "neutral" {
  if (level === "GREEN") return "success";
  if (level === "YELLOW") return "warning";
  if (level === "RED") return "danger";
  return "neutral";
}

function PredictionBanner({ prediction }: { prediction: Record<string, unknown> }) {
  const direction = str(prediction.direction, "Stable");
  const label = str(prediction.label, "Stable");
  const path = str(prediction.mtf_path_display, "");
  const tone =
    direction === "Approaching Trade"
      ? "success"
      : direction === "Moving Away"
        ? "danger"
        : "neutral";

  return (
    <div
      className={cn(
        "border px-4 py-4",
        tone === "success" && "border-[var(--success)]/35 bg-[var(--success)]/8",
        tone === "danger" && "border-[var(--danger)]/35 bg-[var(--danger)]/8",
        tone === "neutral" && "border-[var(--border)] bg-[var(--bg)]/40",
      )}
    >
      <p className="text-[10px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        Prediction
      </p>
      <p
        className={cn(
          "mt-1 text-[20px] font-semibold tracking-tight",
          tone === "success" && "text-[var(--success)]",
          tone === "danger" && "text-[var(--danger)]",
          tone === "neutral" && "text-[var(--fg)]",
        )}
      >
        {label}
      </p>
      <p className="mt-1 text-[12px] text-[var(--fg-muted)]">{direction}</p>
      {path ? (
        <p className="mt-3 font-mono text-[13px] tabular-nums text-[var(--fg)]">
          MTF {path}
        </p>
      ) : null}
      <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">
        {str(prediction.note)}
      </p>
    </div>
  );
}

export function OpportunityTimelineWorkspace() {
  const q = useQuery({
    queryKey: ["ite-ops-opportunity-timeline"],
    queryFn: () => iteOpsApi.adaptiveOpportunityTimeline(100),
    retry: false,
    refetchInterval: 8_000,
  });

  if (q.isLoading) return <DeskSkeleton rows={8} />;
  if (q.isError) {
    return (
      <DeskError
        message={
          q.error instanceof Error
            ? q.error.message
            : "Opportunity Timeline unavailable"
        }
        onRetry={() => void q.refetch()}
      />
    );
  }

  const root = asRecord(q.data);
  const series = asRecord(root.series);
  const prediction = asRecord(root.prediction);
  const points = asList(root.points).map(asRecord);
  const count = num(root.count, 0);

  const mtf = parseSeries(series.mtf);
  const quality = parseSeries(series.quality);
  const confluence = parseSeries(series.confluence);
  const opportunity = parseSeries(series.opportunity);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="neutral">OPPORTUNITY TIMELINE</Badge>
        <Badge tone="success">READ-ONLY</Badge>
        <Badge tone="warning">ENGINES UNCHANGED</Badge>
        <Badge tone="neutral">{count}/100 evaluations</Badge>
      </div>

      <PredictionBanner prediction={prediction} />

      <OpsPanel title="Trend charts">
        <div className="grid gap-3 lg:grid-cols-2">
          <OpportunityTrendChart
            title="MTF Trend"
            data={mtf}
            color="var(--accent)"
            yDomain={[0, 100]}
          />
          <OpportunityTrendChart
            title="Quality Trend"
            data={quality}
            color="var(--success)"
            yDomain={[0, 100]}
          />
          <OpportunityTrendChart
            title="Confluence Trend"
            data={confluence}
            color="var(--warning)"
            yDomain={[0, 100]}
          />
          <OpportunityTrendChart
            title="Opportunity Trend"
            data={opportunity}
            color="var(--fg-muted)"
            yDomain={[0, 100]}
          />
        </div>
      </OpsPanel>

      <OpsPanel title={`Live history (last ${count || 0})`}>
        {points.length === 0 ? (
          <DeskEmpty
            icon={LineChart}
            title="No evaluations yet"
            description="Each live ITE cycle appends MTF, Quality, Confluence, Risk Lots, and Opportunity Meter."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-left text-[12px]">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] uppercase tracking-[0.1em] text-[var(--fg-subtle)]">
                  <th className="px-2 py-2 font-medium">Time</th>
                  <th className="px-2 py-2 font-medium">MTF</th>
                  <th className="px-2 py-2 font-medium">Quality</th>
                  <th className="px-2 py-2 font-medium">Confluence</th>
                  <th className="px-2 py-2 font-medium">Risk Lots</th>
                  <th className="px-2 py-2 font-medium">Meter</th>
                  <th className="px-2 py-2 font-medium">Action</th>
                </tr>
              </thead>
              <tbody>
                {points.map((row, i) => {
                  const level = str(row.opportunity_meter, "RED");
                  return (
                    <tr
                      key={`${str(row.signal_id, String(i))}-${str(row.recorded_at)}`}
                      className="border-b border-[var(--border)]/60 font-mono tabular-nums"
                    >
                      <td className="px-2 py-1.5 text-[var(--fg-subtle)]">
                        {str(row.recorded_at)}
                      </td>
                      <td className="px-2 py-1.5 text-[var(--fg)]">
                        {str(row.mtf_score, "—")}
                      </td>
                      <td className="px-2 py-1.5 text-[var(--fg)]">
                        {str(row.quality, "—")}
                      </td>
                      <td className="px-2 py-1.5 text-[var(--fg)]">
                        {str(row.confluence, "—")}
                      </td>
                      <td className="px-2 py-1.5 text-[var(--fg)]">
                        {str(row.risk_lots, "—")}
                      </td>
                      <td className="px-2 py-1.5">
                        <Badge tone={meterTone(level)}>
                          {level}
                          {row.opportunity_meter_label
                            ? ` · ${str(row.opportunity_meter_label)}`
                            : ""}
                        </Badge>
                      </td>
                      <td className="px-2 py-1.5 text-[var(--fg-muted)]">
                        {str(row.decision_action)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </OpsPanel>
    </div>
  );
}
