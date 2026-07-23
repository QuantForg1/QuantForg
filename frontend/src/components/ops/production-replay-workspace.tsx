"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { History, Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DeskEmpty, DeskSkeleton } from "@/components/desk/primitives";
import { productionReplayApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn } from "@/lib/utils";

type Opportunity = {
  timestamp: string;
  session: string;
  signal_id: string;
  quality: number;
  confluence: number;
  action: string;
  risk_result: string;
  safety_result: string;
  would_reach_oms: string;
  would_reach_mt5: string;
  rejection_reason: string;
  latency_ms: number;
};

function toOpportunity(row: unknown): Opportunity {
  const r = asRecord(row);
  return {
    timestamp: str(r.timestamp, "—"),
    session: str(r.session, "—"),
    signal_id: str(r.signal_id, "—"),
    quality: num(r.quality, 0),
    confluence: num(r.confluence, 0),
    action: str(r.action, "—"),
    risk_result: str(r.risk_result, "—"),
    safety_result: str(r.safety_result, "—"),
    would_reach_oms: str(r.would_reach_oms, "NO"),
    would_reach_mt5: str(r.would_reach_mt5, "NO"),
    rejection_reason: str(r.rejection_reason, ""),
    latency_ms: num(r.latency_ms, 0),
  };
}

function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "success" | "danger" | "accent" | "neutral";
}) {
  return (
    <Card>
      <CardHeader>
        <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {label}
        </span>
      </CardHeader>
      <CardContent className="pt-0">
        <div
          className={cn(
            "text-2xl font-semibold tabular-nums",
            tone === "success" && "text-[var(--success)]",
            tone === "danger" && "text-[var(--danger)]",
            tone === "accent" && "text-[var(--accent)]",
          )}
        >
          {value}
        </div>
        {hint ? (
          <p className="mt-1 text-[11px] text-[var(--fg-subtle)]">{hint}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function DistributionBars({
  title,
  data,
}: {
  title: string;
  data: Array<{ label: string; count: number }>;
}) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)] p-3">
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        {title}
      </h3>
      {data.length === 0 ? (
        <p className="text-[11px] text-[var(--fg-subtle)]">No data yet</p>
      ) : (
        <div className="space-y-1.5">
          {data.map((row) => (
            <div key={row.label} className="flex items-center gap-2">
              <span className="w-28 shrink-0 truncate font-mono text-[10px] text-[var(--fg-muted)]">
                {row.label}
              </span>
              <div className="h-3 flex-1 bg-[var(--surface-2)]">
                <div
                  className="h-3 bg-[var(--accent)]"
                  style={{ width: `${Math.max(2, (row.count / max) * 100)}%` }}
                />
              </div>
              <span className="w-8 shrink-0 text-right font-mono text-[10px] text-[var(--fg-subtle)]">
                {row.count}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function reportToMarkdown(report: Record<string, unknown>): string {
  const stats = asRecord(report.statistics);
  const params = asRecord(report.params);
  const opportunities = asList(report.opportunities).map(toOpportunity);
  const lines: string[] = [];
  lines.push("# Production Replay & Validation Report");
  lines.push("");
  lines.push(`- Generated at: \`${str(report.generated_at, "—")}\``);
  lines.push(`- Symbol: \`${str(report.symbol, "—")}\` (gold-only)`);
  lines.push(
    `- Window: last **${str(params.days, "—")}** days · max evaluations **${str(
      params.max_evaluations,
      "—",
    )}** · equity **${str(params.equity, "—")}**`,
  );
  lines.push(
    `- Simulation only — order_send_called: **${String(report.order_send_called ?? false)}**`,
  );
  lines.push("");
  lines.push("## Statistics");
  lines.push("");
  lines.push(`- Total evaluations: **${num(stats.total_evaluations, 0)}**`);
  lines.push(`- Signals (would reach OMS): **${num(stats.signals, 0)}**`);
  lines.push(`- Rejected / no-trade: **${num(stats.rejected, 0)}**`);
  lines.push(`- Average latency: **${num(stats.avg_latency_ms, 0)} ms**`);
  lines.push("");
  lines.push("## Opportunities");
  lines.push("");
  if (opportunities.length === 0) {
    lines.push("_No eligible opportunities in this window._");
  } else {
    lines.push(
      "| Timestamp | Session | Quality | Confluence | Action | Risk | Safety | OMS | Rejection |",
    );
    lines.push("|---|---|---|---|---|---|---|---|---|");
    for (const o of opportunities) {
      lines.push(
        `| ${o.timestamp} | ${o.session} | ${o.quality} | ${o.confluence} | ${o.action} | ${o.risk_result} | ${o.safety_result} | ${o.would_reach_oms} | ${o.rejection_reason || "—"} |`,
      );
    }
  }
  lines.push("");
  return lines.join("\n");
}

export function ProductionReplayWorkspace() {
  const qc = useQueryClient();
  const [days, setDays] = useState("30");
  const [maxEvaluations, setMaxEvaluations] = useState("120");

  const reportQ = useQuery({
    queryKey: ["production-replay-report"],
    queryFn: () => productionReplayApi.report(),
    staleTime: 15_000,
  });

  const runM = useMutation({
    mutationFn: () =>
      productionReplayApi.run({
        days: Number(days) || 30,
        max_evaluations: Number(maxEvaluations) || 120,
      }),
    onSuccess: async (report) => {
      const stats = asRecord(asRecord(report).statistics);
      toast.success(
        `Replay complete — ${num(stats.total_evaluations, 0)} evaluations, ` +
          `${num(stats.signals, 0)} signals (simulation only, no orders sent)`,
      );
      await qc.invalidateQueries({ queryKey: ["production-replay-report"] });
      await qc.invalidateQueries({ queryKey: ["production-replay-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Replay run failed"),
  });

  const report = asRecord(reportQ.data);
  const isEmpty = report.status === "empty" || !report.opportunities;
  const stats = asRecord(report.statistics);
  const opportunities = useMemo(
    () => asList(report.opportunities).map(toOpportunity),
    [report.opportunities],
  );

  const sessionBars = useMemo(
    () =>
      Object.entries(asRecord(stats.session_distribution) as Record<string, number>)
        .map(([label, count]) => ({ label, count: Number(count) || 0 }))
        .sort((a, b) => b.count - a.count),
    [stats.session_distribution],
  );

  const rejectionBars = useMemo(
    () =>
      asList(stats.rejection_reasons_ranked)
        .map((row) => asRecord(row))
        .slice(0, 8)
        .map((row) => ({
          label: str(row.reason, "—").slice(0, 28),
          count: num(row.count, 0),
        })),
    [stats.rejection_reasons_ranked],
  );

  const handleExport = () => {
    if (isEmpty) {
      toast.error("Run a replay first — nothing to export yet");
      return;
    }
    const md = reportToMarkdown(report);
    downloadBlob(
      `production-replay-${str(report.generated_at, "report").replace(/[:.]/g, "-")}.md`,
      md,
      "text/markdown",
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <History className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">
          Production Replay & Validation — simulation only
        </span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Never order_send
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          Gold-only XAUUSD
        </Badge>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1 text-[10px] text-[var(--fg-subtle)]">
            Days
            <input
              value={days}
              onChange={(e) => setDays(e.target.value)}
              className="w-16 border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs"
              aria-label="Days of history"
            />
          </label>
          <label className="flex items-center gap-1 text-[10px] text-[var(--fg-subtle)]">
            Max evals
            <input
              value={maxEvaluations}
              onChange={(e) => setMaxEvaluations(e.target.value)}
              className="w-16 border border-[var(--border)] bg-[var(--bg)] px-2 py-1 text-xs"
              aria-label="Max evaluations"
            />
          </label>
          <Button
            size="sm"
            variant="default"
            disabled={runM.isPending}
            onClick={() => runM.mutate()}
          >
            <Play className="mr-1 size-3.5" />
            {runM.isPending ? "Running…" : "Run replay"}
          </Button>
          <Button size="sm" variant="outline" onClick={handleExport}>
            Export .md
          </Button>
        </div>
      </div>

      {reportQ.isLoading ? <DeskSkeleton rows={4} /> : null}

      {!reportQ.isLoading && isEmpty ? (
        <DeskEmpty
          icon={History}
          title="No replay run yet"
          description="Run a bounded, simulation-only walk-forward replay across London / New York / overlap sessions. Never places an order."
          actionLabel={runM.isPending ? "Running…" : "Run replay"}
          onAction={() => runM.mutate()}
        />
      ) : null}

      {!isEmpty ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Total evaluations"
              value={num(stats.total_evaluations, 0)}
              hint={`of ${num(report.eligible_bars_considered, 0)} eligible M15 closes`}
            />
            <StatCard
              label="Signals (would reach OMS)"
              value={num(stats.signals, 0)}
              tone="success"
            />
            <StatCard
              label="Rejected / no-trade"
              value={num(stats.rejected, 0)}
              tone="danger"
            />
            <StatCard
              label="Avg latency"
              value={`${num(stats.avg_latency_ms, 0)} ms`}
              tone="accent"
            />
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <DistributionBars title="Session distribution" data={sessionBars} />
            <DistributionBars title="Rejection reasons (ranked)" data={rejectionBars} />
          </div>

          <section className="border border-[var(--border)] bg-[var(--surface)]">
            <header className="flex items-center justify-between border-b border-[var(--border)] px-3 py-2">
              <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
                Opportunities
              </h2>
              <span className="font-mono text-[10px] text-[var(--fg-subtle)]">
                {opportunities.length} shown
              </span>
            </header>
            <div className="max-h-[480px] overflow-auto">
              <table className="w-full text-left text-[11px]">
                <thead className="sticky top-0 bg-[var(--surface-2)] text-[var(--fg-subtle)]">
                  <tr>
                    {[
                      "Timestamp",
                      "Session",
                      "Quality",
                      "Confluence",
                      "Action",
                      "Risk",
                      "Safety",
                      "OMS",
                      "MT5",
                      "Rejection reason",
                    ].map((c) => (
                      <th key={c} className="px-2 py-1.5 font-medium uppercase tracking-wide">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {opportunities.map((o, i) => (
                    <tr
                      key={`${o.signal_id}-${i}`}
                      className="border-t border-[var(--border)]/60 font-mono"
                    >
                      <td className="px-2 py-1.5">{o.timestamp.slice(0, 19)}</td>
                      <td className="px-2 py-1.5">{o.session}</td>
                      <td className="px-2 py-1.5">{o.quality}</td>
                      <td className="px-2 py-1.5">{o.confluence}</td>
                      <td className="px-2 py-1.5">{o.action}</td>
                      <td className="px-2 py-1.5">
                        <Badge tone={o.risk_result === "PASS" ? "success" : "danger"}>
                          {o.risk_result}
                        </Badge>
                      </td>
                      <td className="px-2 py-1.5">
                        <Badge tone={o.safety_result === "PASS" ? "success" : "danger"}>
                          {o.safety_result}
                        </Badge>
                      </td>
                      <td className="px-2 py-1.5">
                        <Badge tone={o.would_reach_oms === "YES" ? "accent" : "neutral"}>
                          {o.would_reach_oms}
                        </Badge>
                      </td>
                      <td className="px-2 py-1.5">
                        <Badge tone={o.would_reach_mt5 === "YES" ? "accent" : "neutral"}>
                          {o.would_reach_mt5}
                        </Badge>
                      </td>
                      <td className="max-w-[280px] truncate px-2 py-1.5 text-[var(--fg-subtle)]">
                        {o.rejection_reason || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
