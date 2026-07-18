"use client";

import { memo, useMemo } from "react";
import { Scale } from "lucide-react";
import { Button } from "@/components/ui/button";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";

type Line = { id: string; text: string; tone: "ok" | "warn" | "block" | "neutral" };

/**
 * AI Review — advisory strip from validation / research-lab AI fields.
 * Never invents narrative when API has none.
 */
export const ResearchAiReview = memo(function ResearchAiReview({
  validation,
  collapsed,
  onToggle,
  className,
}: {
  validation: Record<string, unknown> | null;
  collapsed: boolean;
  onToggle: () => void;
  className?: string;
}) {
  const lines = useMemo((): Line[] => {
    if (!validation) {
      return [
        {
          id: "none",
          text: "Run Validate to load an AI research review from the API.",
          tone: "neutral",
        },
      ];
    }
    const review = asRecord(
      validation.ai_research_review ?? validation.ai_review ?? validation.review,
    );
    const next: Line[] = [];
    const verdict = str(review.verdict ?? review.status ?? review.decision);
    if (verdict) {
      const tone =
        /reject|fail|block/i.test(verdict)
          ? "block"
          : /caution|warn|hold/i.test(verdict)
            ? "warn"
            : /pass|approve|ok/i.test(verdict)
              ? "ok"
              : "neutral";
      next.push({ id: "verdict", text: `Verdict · ${verdict}`, tone });
    }
    const conf = num(review.confidence ?? review.score);
    if (Number.isFinite(conf)) {
      next.push({
        id: "conf",
        text: `Confidence ${formatNumber(conf > 1 ? conf : conf * 100, 0)}${conf > 1 ? "" : "%"}`,
        tone: "neutral",
      });
    }
    const reason = str(review.reason ?? review.summary ?? review.narrative);
    if (reason) {
      next.push({ id: "reason", text: reason.slice(0, 160), tone: "neutral" });
    }
    const findings = asList(review.findings ?? review.risks ?? review.notes).map((v) =>
      str(v),
    );
    for (const f of findings.slice(0, 2)) {
      if (f) next.push({ id: `f-${f.slice(0, 12)}`, text: f.slice(0, 120), tone: "warn" });
    }
    if (!next.length) {
      next.push({
        id: "empty",
        text: "Validation returned without an AI review payload.",
        tone: "neutral",
      });
    }
    return next.slice(0, 5);
  }, [validation]);

  const blocked = lines.some((l) => l.tone === "block");
  const warned = lines.some((l) => l.tone === "warn");

  if (collapsed) {
    return (
      <div
        className={cn(
          "flex h-8 shrink-0 items-center justify-between border-b border-[var(--border)] bg-[var(--surface)] px-3",
          className,
        )}
      >
        <div className="flex items-center gap-2">
          <Scale className="h-3.5 w-3.5 text-[var(--fg-subtle)]" aria-hidden />
          <span className="qf-caption">
            AI Review{" "}
            <span
              className={cn(
                "tabular",
                blocked && "text-[var(--danger)]",
                !blocked && warned && "text-[var(--warning)]",
                !blocked && !warned && "text-[var(--fg-muted)]",
              )}
            >
              {blocked ? "block" : warned ? "caution" : "idle"}
            </span>
          </span>
        </div>
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
      aria-label="AI Review"
    >
      <header className="mb-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Scale className="h-3.5 w-3.5 text-[var(--accent)]" aria-hidden />
          <h2 className="qf-label text-[var(--fg)]">AI Review</h2>
          <span className="qf-caption">Advisory · never executes</span>
        </div>
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" onClick={onToggle}>
          Collapse
        </Button>
      </header>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {lines.map((l) => (
          <li
            key={l.id}
            className={cn(
              "text-[11px] leading-snug",
              l.tone === "ok" && "text-[var(--success)]",
              l.tone === "warn" && "text-[var(--warning)]",
              l.tone === "block" && "text-[var(--danger)]",
              l.tone === "neutral" && "text-[var(--fg-muted)]",
            )}
          >
            {l.text}
          </li>
        ))}
      </ul>
    </section>
  );
});
