"use client";

import { memo, useMemo } from "react";
import { asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";
import { ResearchEmpty } from "@/components/research/empty-state";
import type { ResearchStage } from "@/components/research/layout-store";

type Node = {
  id: ResearchStage | string;
  label: string;
  score: number | null;
  detail: string;
};

/**
 * Confidence Timeline — stage-by-stage confidence from real validation artifacts.
 * Missing stages show null (not fabricated scores).
 */
export const ConfidenceTimeline = memo(function ConfidenceTimeline({
  validation,
  walkforwardItem,
  backtestItem,
  strategyPresent,
  hasEvidence,
  className,
}: {
  validation: Record<string, unknown> | null;
  walkforwardItem: Record<string, unknown> | null;
  backtestItem: Record<string, unknown> | null;
  strategyPresent: boolean;
  hasEvidence: boolean;
  className?: string;
}) {
  const nodes = useMemo((): Node[] => {
    const val = asRecord(validation?.validation ?? validation);
    const bt = asRecord(val.backtest ?? backtestItem);
    const wf = asRecord(val.walkforward ?? walkforwardItem);
    const mc = asRecord(val.monte_carlo);
    const review = asRecord(validation?.ai_research_review ?? validation?.ai_review);
    const btMetrics = asRecord(bt.metrics ?? bt);
    const wfMetrics = asRecord(wf.metrics ?? wf);

    const sharpe = num(btMetrics.sharpe_ratio ?? btMetrics.sharpe);
    const pf = num(btMetrics.profit_factor);
    const wr = num(btMetrics.win_rate);
    const robustness = num(wf.robustness ?? wfMetrics.robustness ?? wf.stability_score);
    const mcPass = str(mc.status ?? mc.pass);
    const aiConf = num(review.confidence ?? review.score);

    return [
      {
        id: "idea",
        label: "Idea",
        score: strategyPresent ? 1 : null,
        detail: strategyPresent ? "Strategy in scope" : "Select a strategy",
      },
      {
        id: "observe",
        label: "Observe",
        score: hasEvidence ? 1 : null,
        detail: hasEvidence ? "Artifacts on file" : "No stored evidence",
      },
      {
        id: "validate",
        label: "Validate",
        score: validation ? 1 : null,
        detail: validation ? "Validation artifact" : "Not validated",
      },
      {
        id: "backtest",
        label: "Backtest",
        score: Number.isFinite(sharpe)
          ? Math.min(1, Math.max(0, (sharpe + 1) / 3))
          : Number.isFinite(pf)
            ? Math.min(1, Math.max(0, pf / 2))
            : null,
        detail: Number.isFinite(sharpe)
          ? `Sharpe ${formatNumber(sharpe, 2)}`
          : Number.isFinite(wr)
            ? `Win ${formatNumber(wr, 2)}`
            : "No backtest metrics",
      },
      {
        id: "walkforward",
        label: "Walk-forward",
        score: Number.isFinite(robustness)
          ? Math.min(1, Math.max(0, robustness > 1 ? robustness / 100 : robustness))
          : null,
        detail: Number.isFinite(robustness)
          ? `Robustness ${formatNumber(robustness, 2)}`
          : "No walk-forward",
      },
      {
        id: "risk",
        label: "Risk",
        score:
          mcPass === "pass" || mcPass === "ok"
            ? 1
            : Object.keys(mc).length
              ? 0.5
              : null,
        detail: Object.keys(mc).length
          ? `Monte Carlo · ${mcPass || "recorded"}`
          : "No MC artifact",
      },
      {
        id: "ai",
        label: "AI",
        score: Number.isFinite(aiConf)
          ? Math.min(1, Math.max(0, aiConf > 1 ? aiConf / 100 : aiConf))
          : null,
        detail: Number.isFinite(aiConf)
          ? `Confidence ${formatNumber(aiConf > 1 ? aiConf : aiConf * 100, 0)}`
          : str(review.verdict ?? review.status, "No AI review"),
      },
      {
        id: "promote",
        label: "Promote",
        score: null,
        detail: "Run promotion evaluate",
      },
    ];
  }, [validation, walkforwardItem, backtestItem, strategyPresent, hasEvidence]);

  const hasAny = nodes.some((n) => n.score != null);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        className,
      )}
      aria-label="Confidence Timeline"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Confidence Timeline</h2>
        <p className="qf-caption">Evidence-backed confidence by stage</p>
      </header>
      {!hasAny ? (
        <ResearchEmpty
          title="No confidence path yet"
          description="Validate or load stored backtests / walk-forwards to build the timeline."
        />
      ) : (
        <ol className="min-h-0 flex-1 space-y-2 overflow-y-auto">
          {nodes.map((n) => (
            <li key={n.id} className="space-y-1">
              <div className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className="text-[var(--fg-muted)]">{n.label}</span>
                <span className="tabular text-[var(--fg-subtle)]">
                  {n.score == null ? "—" : `${Math.round(n.score * 100)}%`}
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]">
                <div
                  className={cn(
                    "h-full rounded-full bg-[var(--accent)]",
                    n.score == null && "bg-[var(--border)]",
                  )}
                  style={{ width: `${n.score == null ? 4 : Math.round(n.score * 100)}%` }}
                />
              </div>
              <p className="text-[10px] text-[var(--fg-subtle)]">{n.detail}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
});
