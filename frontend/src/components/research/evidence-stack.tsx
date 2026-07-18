"use client";

import { memo, useMemo } from "react";
import { asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber, formatRelativeTime } from "@/lib/utils";
import { ResearchEmpty } from "@/components/research/empty-state";

type EvidenceRow = {
  id: string;
  kind: string;
  title: string;
  meta: string;
  strategyKey: string;
};

/**
 * Evidence Stack — stored backtests, walk-forwards, compare rows, library hits.
 * Never invents runs.
 */
export const EvidenceStack = memo(function EvidenceStack({
  backtests,
  walkforwards,
  compareItems,
  libraryItems,
  selectedId,
  onSelect,
  className,
}: {
  backtests: Record<string, unknown>[];
  walkforwards: Record<string, unknown>[];
  compareItems: Record<string, unknown>[];
  libraryItems: Record<string, unknown>[];
  selectedId?: string;
  onSelect?: (strategyKey: string) => void;
  className?: string;
}) {
  const rows = useMemo((): EvidenceRow[] => {
    const next: EvidenceRow[] = [];

    for (const b of backtests.slice(0, 20)) {
      const id = str(b.id ?? b.backtest_id);
      const key = str(b.strategy_key, id);
      const m = asRecord(b.metrics);
      next.push({
        id: `bt-${id}`,
        kind: "Backtest",
        title: str(b.name ?? b.strategy_key ?? id, "Backtest"),
        meta: [
          Number.isFinite(num(m.sharpe_ratio))
            ? `Sharpe ${formatNumber(num(m.sharpe_ratio), 2)}`
            : null,
          b.created_at || b.time
            ? formatRelativeTime(String(b.created_at ?? b.time))
            : null,
        ]
          .filter(Boolean)
          .join(" · "),
        strategyKey: key,
      });
    }

    for (const w of walkforwards.slice(0, 15)) {
      const id = str(w.id);
      const key = str(w.strategy_key, id);
      next.push({
        id: `wf-${id}`,
        kind: "Walk-forward",
        title: str(w.name ?? w.strategy_key ?? id, "Walk-forward"),
        meta: [
          Number.isFinite(num(w.robustness))
            ? `Rob ${formatNumber(num(w.robustness), 2)}`
            : null,
          str(w.promotion, ""),
        ]
          .filter(Boolean)
          .join(" · "),
        strategyKey: key,
      });
    }

    for (const c of compareItems.slice(0, 12)) {
      const key = str(c.strategy_key ?? c.key);
      next.push({
        id: `cmp-${key}`,
        kind: "Compare",
        title: str(c.name, key || "Compare"),
        meta: Number.isFinite(num(asRecord(c.metrics).sharpe_ratio))
          ? `Sharpe ${formatNumber(num(asRecord(c.metrics).sharpe_ratio), 2)}`
          : str(c.status, ""),
        strategyKey: key,
      });
    }

    for (const lib of libraryItems.slice(0, 12)) {
      const key = str(lib.strategy_key ?? lib.key);
      next.push({
        id: `lib-${key}`,
        kind: "Library",
        title: str(lib.name, key || "Strategy"),
        meta: str(lib.status ?? lib.state, "saved"),
        strategyKey: key,
      });
    }

    return next;
  }, [backtests, walkforwards, compareItems, libraryItems]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        className,
      )}
      aria-label="Evidence Stack"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Evidence Stack</h2>
        <p className="qf-caption">Stored research artifacts only</p>
      </header>
      {rows.length === 0 ? (
        <ResearchEmpty
          title="No evidence yet"
          description="Backtests, walk-forwards, and library entries appear here when the API has them."
        />
      ) : (
        <ul className="min-h-0 flex-1 space-y-1 overflow-y-auto">
          {rows.map((r) => {
            const active = Boolean(selectedId && r.strategyKey === selectedId);
            return (
              <li key={r.id}>
                <button
                  type="button"
                  className={cn(
                    "flex w-full items-start justify-between gap-2 rounded border border-transparent px-2 py-1.5 text-left text-[11px] hover:bg-[var(--surface-2)]",
                    active && "border-[var(--border)] bg-[var(--surface-2)]",
                  )}
                  onClick={() => {
                    if (r.strategyKey) onSelect?.(r.strategyKey);
                  }}
                >
                  <span>
                    <span className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                      {r.kind}
                    </span>
                    <span className="mt-0.5 block font-medium text-[var(--fg)]">
                      {r.title}
                    </span>
                  </span>
                  <span className="shrink-0 tabular text-[10px] text-[var(--fg-subtle)]">
                    {r.meta || "—"}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
});
