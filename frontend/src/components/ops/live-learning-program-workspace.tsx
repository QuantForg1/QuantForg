"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BookOpen, GraduationCap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { liveLearningProgramApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { asList, asRecord, str } from "@/lib/desk";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { cn } from "@/lib/utils";

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="border border-[var(--border)] bg-[var(--surface)]">
      <header className="border-b border-[var(--border)] px-3 py-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          {title}
        </h2>
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}

function sampleTrades(n: number) {
  const sessions = ["london", "new_york", "asia", "tokyo"];
  return Array.from({ length: n }, (_, i) => ({
    id: `obs_${i}`,
    entry_context: "liquidity sweep reclaim",
    exit_context: i % 3 === 0 ? "stop" : "target",
    market_regime: i % 2 === 0 ? "trend" : "range",
    session: sessions[i % 4],
    spread: 0.18 + (i % 5) * 0.02,
    volatility: i % 5 === 0 ? "elevated" : "normal",
    liquidity: "deep",
    risk_usage: 0.5,
    decision_explanation: "Decision engine approved — advisory record",
    execution_latency: 40 + (i % 20),
    result: i % 3 === 0 ? -12 : 18,
    predicted_confidence: 55 + (i % 40),
    win: i % 3 !== 0,
    day_type: ["trend", "range", "news", "high_vol"][i % 4],
    period: i < n / 2 ? "week_1" : "week_2",
  }));
}

export function LiveLearningProgramWorkspace() {
  const qc = useQueryClient();
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const statusQ = useQuery({
    queryKey: ["llp-status"],
    queryFn: () => liveLearningProgramApi.status(),
    staleTime: 15_000,
  });

  const evaluateM = useMutation({
    mutationFn: () =>
      liveLearningProgramApi.evaluate({
        completed_trades: sampleTrades(40),
        replay_results: {
          expectancy: 4.2,
          win_rate: 58,
          profit_factor: 1.4,
          drawdown: 3.1,
          trade_count: 40,
          avg_latency_ms: 5,
        },
        paper_results: {
          expectancy: 3.1,
          win_rate: 55,
          profit_factor: 1.3,
          drawdown: 3.8,
          trade_count: 36,
          avg_latency_ms: 35,
        },
        live_results: {
          expectancy: 2.4,
          win_rate: 52,
          profit_factor: 1.15,
          drawdown: 4.5,
          trade_count: 40,
          avg_latency_ms: 85,
        },
        operator_feedback: [
          {
            tag: "good_setup",
            note: "Clean London sweep",
            operator: "desk",
          },
          {
            tag: "late_entry",
            note: "Chased NY open",
            operator: "desk",
          },
          {
            tag: "research_idea",
            note: "Test news filter width",
            operator: "research",
          },
        ],
        edge_score_series: [
          { period: "2026-W20", horizon: "weekly", edge_score: 52 },
          { period: "2026-W21", horizon: "weekly", edge_score: 55 },
          { period: "2026-W22", horizon: "weekly", edge_score: 54 },
          { period: "2026-06", horizon: "monthly", edge_score: 53 },
          { period: "2026-07", horizon: "monthly", edge_score: 56 },
        ],
        journal_entries: [
          { day_type: "trend_days", session: "london", note: "Clean trend" },
          { day_type: "news_days", session: "new_york", note: "CPI" },
        ],
      }),
    onSuccess: async (data) => {
      setResult(data);
      const summary = asRecord(data.learning_summary);
      toast.success(
        `LLP · ${str(summary.learning_progress, "—")} · ${str(summary.observation_count, "0")} obs`,
      );
      await qc.invalidateQueries({ queryKey: ["llp-status"] });
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Evaluate failed"),
  });

  const caps = asRecord(statusQ.data?.capabilities);
  const summary = asRecord(asRecord(result).learning_summary);
  const modules = asRecord(asRecord(result).modules);
  const backlog = asList(summary.research_backlog);
  const weekly = asRecord(asRecord(modules.weekly_review).details);
  const topObs = asList(weekly.top_observations);

  if (statusQ.isLoading && !statusQ.data) return <DeskSkeleton rows={6} />;
  if (statusQ.isError && !statusQ.data) {
    return (
      <DeskError
        message={
          statusQ.error instanceof ApiError
            ? statusQ.error.message
            : "LLP unavailable"
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 py-2">
        <GraduationCap className="size-4 text-[var(--fg-muted)]" />
        <span className="text-xs font-medium">
          {TRADING_SYMBOL} Live Learning Program
        </span>
        <Badge tone="accent" className="text-[9px] uppercase">
          Evidence only
        </Badge>
        <Badge tone="success" className="text-[9px] uppercase">
          Never auto-tunes
        </Badge>
        {caps.never_auto_promote_strategies === true ? (
          <Badge tone="neutral" className="text-[9px] uppercase">
            No auto-promote
          </Badge>
        ) : null}
        <span className="ml-auto font-mono text-[10px] text-[var(--fg-subtle)]">
          {str(statusQ.data?.version, "llp")}
        </span>
        <Button
          size="sm"
          disabled={evaluateM.isPending}
          onClick={() => evaluateM.mutate()}
        >
          Run learning cycle
        </Button>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <Panel title="Learning dashboard">
          {!result ? (
            <DeskEmpty
              icon={GraduationCap}
              title="No cycle"
              description="Collect live · paper · replay · feedback"
            />
          ) : (
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Progress</span>
                <span className="font-mono">
                  {str(summary.learning_progress, "—")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Observations</span>
                <span className="font-mono">
                  {str(summary.observation_count, "0")}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Evidence strength</span>
                <span className="font-mono">
                  {str(summary.evidence_strength_pct, "—")}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--fg-muted)]">Coverage</span>
                <span className="font-mono">
                  {str(summary.coverage_pct, "—")}%
                </span>
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">
                Audit {str(result.audit_id, "—")}
              </p>
            </div>
          )}
        </Panel>

        <Panel title="Research backlog">
          {!result ? (
            <DeskEmpty
              icon={BookOpen}
              title="Empty queue"
              description="Recommendations only — never live changes"
            />
          ) : (
            <ul className="max-h-36 space-y-1 overflow-auto font-mono text-[10px]">
              {backlog.length === 0 ? (
                <li className="text-[var(--fg-subtle)]">No recommendations</li>
              ) : (
                backlog.slice(0, 6).map((item) => (
                  <li key={String(item)}>{String(item)}</li>
                ))
              )}
            </ul>
          )}
        </Panel>

        <Panel title="Guarantees">
          <ul className="space-y-1 text-[10px] text-[var(--fg-muted)]">
            <li>Never places trades</li>
            <li>Never modifies strategy / Risk / Safety / Decision</li>
            <li>Never modifies Execution Pipeline</li>
            <li>Never auto-tunes parameters</li>
            <li>Never auto-promotes strategies</li>
          </ul>
          {topObs.length > 0 ? (
            <p className="mt-2 text-[10px] text-[var(--fg-subtle)] line-clamp-3">
              {String(topObs[0])}
            </p>
          ) : null}
        </Panel>
      </div>

      <Panel title="Modules">
        {!Object.keys(modules).length ? (
          <DeskEmpty
            icon={GraduationCap}
            title="No modules"
            description="Observations → recommendations"
          />
        ) : (
          <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
            {Object.entries(modules).map(([key, val]) => {
              const row = asRecord(val);
              return (
                <li
                  key={key}
                  className={cn(
                    "border px-2 py-2",
                    row.status === "insufficient_evidence"
                      ? "border-[var(--warning)]/40"
                      : "border-[var(--border)]",
                  )}
                >
                  <p className="text-[10px] font-medium leading-tight">
                    {str(row.module, key).replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-[var(--fg-subtle)]">
                    {str(row.status, "—")} · {str(row.score, "—")}
                  </p>
                  <p className="mt-1 text-[9px] text-[var(--fg-muted)] line-clamp-2">
                    {str(row.recommendation, "")}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
