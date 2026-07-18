"use client";

import { memo, useMemo } from "react";
import { asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";
import { CounselEmpty } from "@/components/counsel/empty-state";

/**
 * Learning Memory — paper performance + session analysis from APIs.
 */
export const LearningMemory = memo(function LearningMemory({
  paperPerformance,
  sessionAnalysis,
  focused,
  className,
}: {
  paperPerformance: Record<string, unknown> | null;
  sessionAnalysis: Record<string, unknown> | null;
  focused?: boolean;
  className?: string;
}) {
  const rows = useMemo(() => {
    const next: { label: string; value: string }[] = [];
    if (paperPerformance) {
      const p = paperPerformance;
      const metrics = asRecord(p.metrics ?? p);
      const addNum = (label: string, key: string) => {
        const v = num(metrics[key] ?? p[key]);
        if (Number.isFinite(v)) next.push({ label, value: formatNumber(v, 2) });
      };
      addNum("Wait ratio", "wait_ratio");
      addNum("Ideas", "trade_ideas");
      addNum("Waits", "waits");
      addNum("Win rate", "win_rate");
      if (str(p.reason)) next.push({ label: "Note", value: str(p.reason).slice(0, 100) });
    }
    if (sessionAnalysis) {
      if (str(sessionAnalysis.summary)) {
        next.push({ label: "Session", value: str(sessionAnalysis.summary).slice(0, 100) });
      }
      const score = num(sessionAnalysis.score ?? sessionAnalysis.quality);
      if (Number.isFinite(score)) {
        next.push({ label: "Session score", value: formatNumber(score, 2) });
      }
    }
    return next;
  }, [paperPerformance, sessionAnalysis]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Learning Memory"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Learning Memory</h2>
        <p className="qf-caption">Paper edge · session notes</p>
      </header>
      {rows.length === 0 ? (
        <CounselEmpty
          title="Nothing learned yet"
          description="Record TRADE_IDEA outcomes and session analysis to build memory — never fabricated."
        />
      ) : (
        <dl className="min-h-0 flex-1 space-y-1.5 overflow-y-auto text-[11px]">
          {rows.map((r) => (
            <div
              key={r.label}
              className="flex justify-between gap-3 border-b border-[var(--border)] py-1"
            >
              <dt className="text-[var(--fg-subtle)]">{r.label}</dt>
              <dd className="text-right text-[var(--fg)]">{r.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
});
