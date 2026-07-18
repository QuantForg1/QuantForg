"use client";

import { memo, useMemo } from "react";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";
import { CounselEmpty } from "@/components/counsel/empty-state";

/**
 * Context Lens — market / MTF / session context from DE + intelligence.
 */
export const ContextLens = memo(function ContextLens({
  decisionRoot,
  marketContext,
  quantAssistant,
  focused,
  className,
}: {
  decisionRoot: Record<string, unknown> | null;
  marketContext: Record<string, unknown> | null;
  quantAssistant: Record<string, unknown> | null;
  focused?: boolean;
  className?: string;
}) {
  const rows = useMemo(() => {
    const next: { label: string; value: string }[] = [];
    const decision = asRecord(decisionRoot?.decision ?? decisionRoot);
    const analysis = asRecord(decision.analysis);
    const mtf = asRecord(decision.multi_timeframe);

    const push = (label: string, value: unknown) => {
      const v = str(value);
      if (v) next.push({ label, value: v });
    };

    push("Trend", analysis.trend);
    push("Structure", analysis.structure);
    push("Session", analysis.session);
    push("Volatility", analysis.volatility ?? analysis.vol);
    push("Spread", analysis.spread);
    push("News risk", analysis.news_risk);
    push("Correlation", analysis.correlation_risk);
    if (mtf.aligned === true) next.push({ label: "MTF", value: "Aligned" });
    if (mtf.aligned === false) next.push({ label: "MTF", value: "Not aligned" });
    push("MTF why", mtf.why);

    const frames = asRecord(mtf.frames);
    for (const [tf, raw] of Object.entries(frames).slice(0, 4)) {
      const f = asRecord(raw);
      const conf = num(f.confidence_pct);
      next.push({
        label: tf,
        value: `${str(f.trend, "—")}${
          Number.isFinite(conf) ? ` · ${formatNumber(conf, 0)}%` : ""
        }`,
      });
    }

    if (quantAssistant) {
      push("QA trend", quantAssistant.trend);
      push("QA momentum", quantAssistant.momentum);
      push("QA vol", quantAssistant.volatility);
    }

    if (marketContext) {
      push("Context", marketContext.summary ?? marketContext.narrative ?? marketContext.headline);
      const risks = asList(marketContext.risk_factors ?? marketContext.risks)
        .map((v) => str(v))
        .filter(Boolean);
      if (risks[0]) next.push({ label: "Context risk", value: risks[0].slice(0, 100) });
    }

    return next.slice(0, 14);
  }, [decisionRoot, marketContext, quantAssistant]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Context Lens"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Context Lens</h2>
        <p className="qf-caption">Live analysis fields only</p>
      </header>
      {rows.length === 0 ? (
        <CounselEmpty
          title="No context"
          description="Decision Engine analysis and market context appear when the APIs respond."
        />
      ) : (
        <dl className="min-h-0 flex-1 space-y-1.5 overflow-y-auto text-[11px]">
          {rows.map((r) => (
            <div
              key={r.label}
              className="flex justify-between gap-3 border-b border-[var(--border)] py-1"
            >
              <dt className="shrink-0 text-[var(--fg-subtle)]">{r.label}</dt>
              <dd className="text-right text-[var(--fg)]">{r.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
});
