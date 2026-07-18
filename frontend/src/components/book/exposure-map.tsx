"use client";

import { memo, useMemo } from "react";
import { allocationFromPositions, classifySymbol } from "@/lib/dashboard/derive";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import { BookEmpty } from "@/components/book/empty-state";

/**
 * Exposure Map — symbol + asset-class heat from live positions (and optional PI sectors).
 */
export const ExposureMap = memo(function ExposureMap({
  positions,
  freeMargin,
  intelligence,
  focused,
  className,
}: {
  positions: Record<string, unknown>[];
  freeMargin: number;
  intelligence: Record<string, unknown> | null;
  focused?: boolean;
  className?: string;
}) {
  const byClass = useMemo(
    () => allocationFromPositions(positions, freeMargin),
    [positions, freeMargin],
  );

  const bySymbol = useMemo(() => {
    const rows = positions.map((p) => {
      const symbol = str(p.symbol, "—");
      const notional = Math.abs(
        num(p.volume, 0) * num(p.current_price ?? p.open_price, 0),
      );
      const pnl = num(p.profit, 0);
      return {
        symbol,
        classKey: classifySymbol(symbol),
        notional: Number.isFinite(notional) ? notional : 0,
        pnl,
      };
    });
    const total = rows.reduce((s, r) => s + r.notional, 0) || 1;
    return rows
      .map((r) => ({ ...r, weight: (r.notional / total) * 100 }))
      .sort((a, b) => b.notional - a.notional)
      .slice(0, 12);
  }, [positions]);

  const sectors = useMemo(() => {
    if (!intelligence) return [];
    const risk = asRecord(intelligence.risk);
    return asList(risk.sector_allocation)
      .map(asRecord)
      .map((s) => ({
        name: str(s.sector, "—"),
        weight: num(s.weight_pct, 0),
      }))
      .filter((s) => Number.isFinite(s.weight) && s.weight > 0)
      .slice(0, 8);
  }, [intelligence]);

  const maxClass = Math.max(...byClass.map((c) => c.value), 1);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Exposure Map"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Exposure Map</h2>
        <p className="qf-caption">Where capital sits right now</p>
      </header>

      {!positions.length && !sectors.length ? (
        <BookEmpty
          title="No exposure"
          description="Open positions map here. Flat books show an empty state — never a fake allocation."
        />
      ) : (
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
          {byClass.length > 0 ? (
            <div>
              <p className="mb-1.5 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Asset class
              </p>
              <ul className="space-y-1.5">
                {byClass.map((c) => (
                  <li key={c.classKey} className="flex items-center gap-2 text-[11px]">
                    <span className="w-20 shrink-0 truncate text-[var(--fg-muted)]">
                      {c.name}
                    </span>
                    <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-[var(--surface-2)]">
                      <div
                        className="h-full rounded-full bg-[var(--accent)]"
                        style={{
                          width: `${Math.round((c.value / maxClass) * 100)}%`,
                        }}
                      />
                    </div>
                    <span className="w-16 shrink-0 text-right tabular text-[var(--fg)]">
                      {formatCurrency(c.value)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {bySymbol.length > 0 ? (
            <div>
              <p className="mb-1.5 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Symbols
              </p>
              <ul className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
                {bySymbol.map((r) => (
                  <li
                    key={r.symbol}
                    className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1.5"
                  >
                    <div className="flex items-baseline justify-between gap-1">
                      <span className="truncate font-medium text-[var(--fg)]">
                        {r.symbol}
                      </span>
                      <span className="tabular text-[10px] text-[var(--fg-subtle)]">
                        {formatNumber(r.weight, 0)}%
                      </span>
                    </div>
                    <p
                      className={cn(
                        "tabular text-[10px]",
                        r.pnl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
                      )}
                    >
                      {formatCurrency(r.pnl)}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {sectors.length > 0 ? (
            <div>
              <p className="mb-1.5 text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
                Sector (intelligence)
              </p>
              <ul className="flex flex-wrap gap-1.5">
                {sectors.map((s) => (
                  <li
                    key={s.name}
                    className="rounded border border-[var(--border)] px-2 py-0.5 text-[10px] text-[var(--fg-muted)]"
                  >
                    {s.name}{" "}
                    <span className="tabular text-[var(--fg)]">
                      {formatNumber(s.weight, 1)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
});
