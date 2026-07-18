"use client";

import { memo } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { CounselRecommendation } from "@/components/counsel/recommendation-model";

/**
 * Silence Protocol — first-class WAIT / hold state.
 * When Counsel has nothing actionable, silence is the product.
 */
export const SilenceProtocol = memo(function SilenceProtocol({
  recommendation,
  apiError,
  expanded,
  onToggle,
  className,
}: {
  recommendation: CounselRecommendation | null;
  apiError: boolean;
  expanded: boolean;
  onToggle: () => void;
  className?: string;
}) {
  const silent =
    apiError ||
    !recommendation ||
    recommendation.action === "WAIT" ||
    recommendation.approval === "held" ||
    recommendation.approval === "unavailable";

  if (!silent) {
    return (
      <div
        className={cn(
          "flex h-8 shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-3",
          className,
        )}
      >
        <p className="qf-caption text-[var(--accent)]">
          Silence Protocol inactive — TRADE_IDEA under review (advisory)
        </p>
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" onClick={onToggle}>
          {expanded ? "Collapse" : "Expand"}
        </Button>
      </div>
    );
  }

  if (!expanded) {
    return (
      <div
        className={cn(
          "flex h-8 shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-3",
          className,
        )}
        role="status"
      >
        <p className="qf-caption text-[var(--warning)]">
          Silence Protocol · WAIT
        </p>
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" onClick={onToggle}>
          Expand
        </Button>
      </div>
    );
  }

  return (
    <section
      className={cn(
        "shrink-0 border-b border-[var(--border)] bg-[var(--surface)] px-3 py-2",
        className,
      )}
      aria-label="Silence Protocol"
      role="status"
    >
      <header className="mb-1 flex items-center justify-between gap-2">
        <h2 className="qf-label text-[var(--warning)]">Silence Protocol</h2>
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" onClick={onToggle}>
          Collapse
        </Button>
      </header>
      <p className="text-[11px] leading-relaxed text-[var(--fg-muted)]">
        {apiError
          ? "Decision Engine unavailable — stance remains WAIT. Counsel will not invent a trade."
          : recommendation?.approval === "unavailable"
            ? recommendation.reason || "Unable to evaluate — WAIT."
            : recommendation?.reason ||
              "No trade idea clears the gate. Capital preservation is the default. Terminal stays quiet until you decide otherwise."}
      </p>
    </section>
  );
});
