"use client";

import { memo, useMemo } from "react";
import { asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";
import { ResearchEmpty } from "@/components/research/empty-state";

/**
 * Strategy DNA — fingerprint of the selected strategy from catalog / library.
 * Real fields only; never invents parameters or edge.
 */
export const StrategyDna = memo(function StrategyDna({
  catalogItem,
  libraryItem,
  strategyKey,
  className,
}: {
  catalogItem: Record<string, unknown> | null;
  libraryItem: Record<string, unknown> | null;
  strategyKey: string;
  className?: string;
}) {
  const strands = useMemo(() => {
    const src = libraryItem || catalogItem;
    if (!src) return [];
    const params = asRecord(src.parameters ?? src.default_params ?? src.params);
    const paramKeys = Object.keys(params).slice(0, 8);
    const rows: { label: string; value: string }[] = [
      {
        label: "Key",
        value: str(src.strategy_key ?? src.key ?? src.id, strategyKey || "—"),
      },
      { label: "Name", value: str(src.name ?? src.title, "—") },
      { label: "Family", value: str(src.family ?? src.category ?? src.type, "—") },
      { label: "Status", value: str(src.status ?? src.state, "—") },
      {
        label: "Trades (saved)",
        value: Number.isFinite(num(src.trade_count ?? asRecord(src.metrics).trade_count))
          ? formatNumber(num(src.trade_count ?? asRecord(src.metrics).trade_count), 0)
          : "—",
      },
      {
        label: "Sharpe (saved)",
        value: Number.isFinite(num(asRecord(src.metrics).sharpe_ratio ?? src.sharpe))
          ? formatNumber(num(asRecord(src.metrics).sharpe_ratio ?? src.sharpe), 2)
          : "—",
      },
    ];
    for (const k of paramKeys) {
      rows.push({ label: `Param · ${k}`, value: String(params[k] ?? "—") });
    }
    return rows;
  }, [catalogItem, libraryItem, strategyKey]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        className,
      )}
      aria-label="Strategy DNA"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Strategy DNA</h2>
        <p className="qf-caption">Identity & parameters — catalog / library only</p>
      </header>
      {strands.length === 0 ? (
        <ResearchEmpty
          title="No strategy selected"
          description="Pick a catalog or library strategy to inspect its DNA."
        />
      ) : (
        <dl className="min-h-0 flex-1 space-y-1.5 overflow-y-auto text-[11px]">
          {strands.map((r) => (
            <div key={r.label} className="flex justify-between gap-3 border-b border-[var(--border)] py-1">
              <dt className="shrink-0 text-[var(--fg-subtle)]">{r.label}</dt>
              <dd className="truncate text-right font-mono tabular text-[var(--fg)]">
                {r.value}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
});
