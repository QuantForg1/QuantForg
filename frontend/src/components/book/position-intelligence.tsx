"use client";

import { memo, useMemo } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { classifySymbol, durationLabel } from "@/lib/dashboard/derive";
import { num, str } from "@/lib/desk";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import { BookEmpty } from "@/components/book/empty-state";

/**
 * Position Intelligence — ranked open risk with actionable next step to Terminal.
 */
export const PositionIntelligence = memo(function PositionIntelligence({
  positions,
  focused,
  className,
}: {
  positions: Record<string, unknown>[];
  focused?: boolean;
  className?: string;
}) {
  const ranked = useMemo(() => {
    return [...positions]
      .map((p) => {
        const profit = num(p.profit, 0);
        const volume = num(p.volume, 0);
        const price = num(p.current_price ?? p.open_price, 0);
        const notional = Math.abs(volume * price);
        const riskScore =
          (Number.isFinite(notional) ? notional : 0) + Math.abs(profit) * 2;
        return { p, profit, volume, notional, riskScore };
      })
      .sort((a, b) => b.riskScore - a.riskScore);
  }, [positions]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Position Intelligence"
    >
      <header className="mb-2 flex shrink-0 items-baseline justify-between gap-2">
        <div>
          <h2 className="qf-label text-[var(--fg)]">Position Intelligence</h2>
          <p className="qf-caption">Ranked by risk weight · live book</p>
        </div>
        <Button size="sm" variant="ghost" className="h-6 px-2 text-[10px]" asChild>
          <Link href="/terminal">Trade</Link>
        </Button>
      </header>

      {ranked.length === 0 ? (
        <BookEmpty
          title="No open positions"
          description="When the book carries risk, positions rank here by weight and P&L."
          action={
            <Button size="sm" variant="secondary" asChild>
              <Link href="/terminal">Open Terminal</Link>
            </Button>
          }
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full text-left text-[11px]">
            <thead className="sticky top-0 bg-[var(--surface)] text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
              <tr>
                <th className="py-1 pr-2 font-medium">Symbol</th>
                <th className="py-1 pr-2 font-medium">Side</th>
                <th className="py-1 pr-2 text-right font-medium">Vol</th>
                <th className="py-1 pr-2 text-right font-medium">P&L</th>
                <th className="py-1 text-right font-medium">Age</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map(({ p, profit, volume }) => {
                const symbol = str(p.symbol, "—");
                return (
                  <tr
                    key={str(p.ticket, symbol)}
                    className="border-t border-[var(--border)]"
                  >
                    <td className="py-1.5 pr-2">
                      <Link
                        href={`/terminal?symbol=${encodeURIComponent(symbol)}`}
                        className="font-medium text-[var(--fg)] hover:text-[var(--accent)]"
                      >
                        {symbol}
                      </Link>
                      <span className="ml-1 text-[10px] text-[var(--fg-subtle)]">
                        {classifySymbol(symbol)}
                      </span>
                    </td>
                    <td className="py-1.5 pr-2 uppercase text-[var(--fg-muted)]">
                      {str(p.side, "—")}
                    </td>
                    <td className="py-1.5 pr-2 text-right tabular">
                      {Number.isFinite(volume) ? formatNumber(volume, 2) : "—"}
                    </td>
                    <td
                      className={cn(
                        "py-1.5 pr-2 text-right tabular",
                        profit >= 0
                          ? "text-[var(--success)]"
                          : "text-[var(--danger)]",
                      )}
                    >
                      {formatCurrency(profit)}
                    </td>
                    <td className="py-1.5 text-right tabular text-[var(--fg-subtle)]">
                      {durationLabel(p.open_time ?? p.time)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
});
