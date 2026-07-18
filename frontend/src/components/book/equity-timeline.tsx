"use client";

import { memo } from "react";
import { LazyEquityChart } from "@/components/charts/lazy";
import { cn } from "@/lib/utils";
import { BookEmpty } from "@/components/book/empty-state";

/**
 * Equity Timeline — reconstructed from live deals + seed equity only.
 */
export const EquityTimeline = memo(function EquityTimeline({
  series,
  focused,
  className,
}: {
  series: { t: string; equity: number }[];
  focused?: boolean;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Equity Timeline"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Equity Timeline</h2>
        <p className="qf-caption">Built from synced deals — never fabricated</p>
      </header>
      <div className="min-h-0 flex-1">
        {series.length === 0 ? (
          <BookEmpty
            title="No equity history"
            description="When deals sync from the live book, the equity path appears here."
          />
        ) : (
          <div className="h-full min-h-[140px]">
            <LazyEquityChart data={series} emptyLabel="No equity history" />
          </div>
        )}
      </div>
    </section>
  );
});
