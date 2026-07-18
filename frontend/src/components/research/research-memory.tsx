"use client";

import { memo, useMemo } from "react";
import { asList, asRecord, str } from "@/lib/desk";
import { cn, formatRelativeTime } from "@/lib/utils";
import { ResearchEmpty } from "@/components/research/empty-state";

/**
 * Research Memory — dashboard leaders, regime, paper snapshot, library preview.
 * Real research-lab fields only.
 */
export const ResearchMemory = memo(function ResearchMemory({
  dashboard,
  paper,
  regime,
  className,
}: {
  dashboard: Record<string, unknown> | null;
  paper: Record<string, unknown> | null;
  regime: Record<string, unknown> | null;
  className?: string;
}) {
  const memories = useMemo(() => {
    if (!dashboard && !paper && !regime) return [];
    const leaders = asRecord(dashboard?.research_dashboard ?? dashboard);
    const best = asRecord(leaders.best);
    const worst = asRecord(leaders.worst);
    const candidate = asRecord(leaders.candidate);
    const preview = asList(dashboard?.library_preview).map(asRecord);
    const rows: { title: string; body: string }[] = [];

    if (Object.keys(candidate).length) {
      rows.push({
        title: "Candidate",
        body: str(candidate.name, str(candidate.strategy_key, "—")),
      });
    }
    if (Object.keys(best).length) {
      rows.push({
        title: "Best on file",
        body: str(best.name, str(best.strategy_key, "—")),
      });
    }
    if (Object.keys(worst).length) {
      rows.push({
        title: "Weakest on file",
        body: str(worst.name, str(worst.strategy_key, "—")),
      });
    }
    if (regime && Object.keys(regime).length) {
      rows.push({
        title: "Regime",
        body: str(regime.label ?? regime.regime ?? regime.name, "—"),
      });
    }
    if (paper && Object.keys(paper).length) {
      rows.push({
        title: "Paper desk",
        body: str(
          paper.status ?? paper.summary,
          `trades ${str(asRecord(paper.metrics).trade_count, "—")}`,
        ),
      });
    }
    for (const p of preview.slice(0, 4)) {
      rows.push({
        title: "Library",
        body: `${str(p.name, str(p.strategy_key))} · ${
          p.updated_at
            ? formatRelativeTime(String(p.updated_at))
            : str(p.status, "saved")
        }`,
      });
    }
    return rows;
  }, [dashboard, paper, regime]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        className,
      )}
      aria-label="Research Memory"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Research Memory</h2>
        <p className="qf-caption">Leaders, regime, paper — from research lab</p>
      </header>
      {memories.length === 0 ? (
        <ResearchEmpty
          title="Memory empty"
          description="When research-lab has leaders or library previews, they surface here."
        />
      ) : (
        <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto">
          {memories.map((m, i) => (
            <li
              key={`${m.title}-${i}`}
              className="border-b border-[var(--border)] pb-2 text-[11px]"
            >
              <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                {m.title}
              </p>
              <p className="mt-0.5 text-[var(--fg)]">{m.body}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
});
