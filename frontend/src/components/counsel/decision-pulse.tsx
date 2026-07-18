"use client";

import { memo } from "react";
import { cn, formatNumber } from "@/lib/utils";
import type { CounselRecommendation } from "@/components/counsel/recommendation-model";
import { CounselEmpty } from "@/components/counsel/empty-state";

/**
 * Decision Pulse — current stance at a glance.
 */
export const DecisionPulse = memo(function DecisionPulse({
  recommendation,
  focused,
  className,
}: {
  recommendation: CounselRecommendation | null;
  focused?: boolean;
  className?: string;
}) {
  if (!recommendation) {
    return (
      <section
        className={cn(
          "rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
          focused && "ring-1 ring-[var(--accent)]",
          className,
        )}
        aria-label="Decision Pulse"
      >
        <h2 className="qf-label mb-2 text-[var(--fg)]">Decision Pulse</h2>
        <CounselEmpty
          title="No decision yet"
          description="Evaluate or wait for the Decision Engine dashboard. Default stance is WAIT."
        />
      </section>
    );
  }

  const isWait = recommendation.action === "WAIT";

  return (
    <section
      className={cn(
        "rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Decision Pulse"
    >
      <header className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="qf-label text-[var(--fg)]">Decision Pulse</h2>
        <span className="qf-caption font-mono">{recommendation.symbol}</span>
      </header>
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <p className="qf-caption text-[var(--fg-subtle)]">Stance</p>
          <p
            className={cn(
              "font-mono text-2xl font-semibold tabular tracking-tight",
              isWait ? "text-[var(--warning)]" : "text-[var(--accent)]",
            )}
          >
            {recommendation.action}
          </p>
        </div>
        <div>
          <p className="qf-caption text-[var(--fg-subtle)]">Confidence</p>
          <p className="font-mono text-lg tabular text-[var(--fg)]">
            {recommendation.confidence == null
              ? "—"
              : `${formatNumber(recommendation.confidence, 0)}%`}
          </p>
        </div>
        <div>
          <p className="qf-caption text-[var(--fg-subtle)]">Approval</p>
          <p className="text-sm capitalize text-[var(--fg-muted)]">
            {recommendation.approval.replace(/_/g, " ")}
          </p>
        </div>
        <div>
          <p className="qf-caption text-[var(--fg-subtle)]">Risk</p>
          <p className="text-sm text-[var(--fg-muted)]">{recommendation.riskLevel}</p>
        </div>
      </div>
    </section>
  );
});
