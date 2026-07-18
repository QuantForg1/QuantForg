"use client";

import { memo, useMemo } from "react";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber, formatRelativeTime } from "@/lib/utils";
import { CounselEmpty } from "@/components/counsel/empty-state";

/**
 * Decision Timeline — paper recent + reports from Decision Engine.
 */
export const DecisionTimeline = memo(function DecisionTimeline({
  paperRecent,
  reports,
  focused,
  className,
}: {
  paperRecent: Record<string, unknown>[];
  reports: Record<string, unknown> | null;
  focused?: boolean;
  className?: string;
}) {
  const events = useMemo(() => {
    const next: { id: string; title: string; meta: string }[] = [];

    for (const r of paperRecent.slice(0, 20)) {
      const id = str(r.id ?? r.created_at ?? r.symbol, String(next.length));
      next.push({
        id: `paper-${id}`,
        title: `${str(r.decision ?? r.action, "—")} · ${str(r.symbol, "—")}`,
        meta: [
          Number.isFinite(num(r.confidence_pct))
            ? `${formatNumber(num(r.confidence_pct), 0)}%`
            : null,
          r.created_at || r.time
            ? formatRelativeTime(String(r.created_at ?? r.time))
            : null,
        ]
          .filter(Boolean)
          .join(" · "),
      });
    }

    const items = asList(reports?.items ?? reports?.recent).map(asRecord);
    for (const r of items.slice(0, 10)) {
      next.push({
        id: `rep-${str(r.id, String(next.length))}`,
        title: str(r.title ?? r.type ?? r.decision, "Report"),
        meta: str(r.status, r.created_at ? formatRelativeTime(String(r.created_at)) : ""),
      });
    }

    return next;
  }, [paperRecent, reports]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Decision Timeline"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Decision Timeline</h2>
        <p className="qf-caption">Paper outcomes & reports</p>
      </header>
      {events.length === 0 ? (
        <CounselEmpty
          title="No decision history"
          description="Paper evaluations and reports appear here when recorded by the API."
        />
      ) : (
        <ol className="min-h-0 flex-1 space-y-2 overflow-y-auto">
          {events.map((e) => (
            <li
              key={e.id}
              className="border-b border-[var(--border)] pb-2 text-[11px]"
            >
              <p className="font-medium text-[var(--fg)]">{e.title}</p>
              <p className="tabular text-[10px] text-[var(--fg-subtle)]">
                {e.meta || "—"}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
});
