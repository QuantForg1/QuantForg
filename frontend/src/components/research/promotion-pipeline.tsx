"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";
import {
  RESEARCH_STAGES,
  type ResearchStage,
} from "@/components/research/layout-store";

/**
 * Promotion Pipeline — workflow chrome for Research OS.
 * Idea → … → Promote. Stages are advisory; never places trades.
 */
export const PromotionPipeline = memo(function PromotionPipeline({
  stage,
  onStageChange,
  className,
}: {
  stage: ResearchStage;
  onStageChange: (s: ResearchStage) => void;
  className?: string;
}) {
  const idx = RESEARCH_STAGES.findIndex((s) => s.id === stage);

  return (
    <nav
      className={cn(
        "flex shrink-0 items-center gap-0.5 overflow-x-auto border-b border-[var(--border)] bg-[var(--bg-elevated)] px-2 py-1.5",
        className,
      )}
      aria-label="Research promotion pipeline"
    >
      {RESEARCH_STAGES.map((s, i) => {
        const active = s.id === stage;
        const done = i < idx;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onStageChange(s.id)}
            className={cn(
              "flex shrink-0 items-center gap-1 rounded px-2 py-1 text-[11px] transition-colors duration-200",
              active && "bg-[var(--surface-2)] text-[var(--fg)]",
              !active && done && "text-[var(--success)]",
              !active && !done && "text-[var(--fg-subtle)] hover:text-[var(--fg-muted)]",
            )}
            aria-current={active ? "step" : undefined}
          >
            <span className="font-mono text-[9px] text-[var(--fg-subtle)]">
              {s.hotkey}
            </span>
            {s.label}
            {i < RESEARCH_STAGES.length - 1 ? (
              <span className="ml-1 text-[var(--border-strong)]" aria-hidden>
                →
              </span>
            ) : null}
          </button>
        );
      })}
    </nav>
  );
});
