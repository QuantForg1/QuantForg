"use client";

import { memo, useMemo } from "react";
import { metric, num } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";
import {
  computeTradeAnalytics,
  parseLiveDeal,
  pairDealsIntoTrades,
} from "@/lib/orders/history";

/**
 * Book Portfolio Overview — live MT5 account + deal-derived returns only.
 * Missing metrics render as Not available (never invented).
 */
export const PortfolioOverview = memo(function PortfolioOverview({
  account,
  positions,
  deals,
  className,
}: {
  account: Record<string, unknown>;
  positions: Record<string, unknown>[];
  deals: Record<string, unknown>[];
  className?: string;
}) {
  const balance = metric(account, "balance");
  const equity = metric(account, "equity");
  const margin = metric(account, "margin");
  const freeMargin = metric(account, "free_margin");
  const marginLevel = metric(account, "margin_level");
  const floating = metric(account, "profit");

  const analytics = useMemo(() => {
    const parsed = deals
      .map((d) => parseLiveDeal(d))
      .filter((d): d is NonNullable<typeof d> => d != null);
    const trades = pairDealsIntoTrades(parsed);
    return computeTradeAnalytics(trades, { startingEquity: 0 });
  }, [deals]);

  const allocation = useMemo(() => {
    const map = new Map<string, number>();
    for (const p of positions) {
      const sym = String(p.symbol || "—").toUpperCase();
      const vol = num(p.volume, 0);
      map.set(sym, (map.get(sym) ?? 0) + vol);
    }
    const total = [...map.values()].reduce((a, b) => a + b, 0) || 1;
    return [...map.entries()].map(([label, value]) => ({
      label,
      value,
      pct: (value / total) * 100,
    }));
  }, [positions]);

  const totalReturn = analytics.closedCount
    ? analytics.todayPl !== undefined
      ? analytics.monthPl // display month as proxy when no inception equity
      : null
    : null;

  const cells: { label: string; value: string; tone?: string }[] = [
    {
      label: "Balance",
      value: Number.isFinite(balance) ? formatNumber(balance, 2) : "Not available",
    },
    {
      label: "Equity",
      value: Number.isFinite(equity) ? formatNumber(equity, 2) : "Not available",
    },
    {
      label: "Margin",
      value: Number.isFinite(margin) ? formatNumber(margin, 2) : "Not available",
    },
    {
      label: "Free Margin",
      value: Number.isFinite(freeMargin) ? formatNumber(freeMargin, 2) : "Not available",
    },
    {
      label: "Margin Level",
      value: Number.isFinite(marginLevel) ? `${formatNumber(marginLevel, 1)}%` : "Not available",
    },
    {
      label: "Open Positions",
      value: String(positions.length),
    },
    {
      label: "Floating P/L",
      value: Number.isFinite(floating) ? formatNumber(floating, 2) : "Not available",
      tone:
        Number.isFinite(floating) && floating > 0
          ? "text-[var(--success)]"
          : Number.isFinite(floating) && floating < 0
            ? "text-[var(--danger)]"
            : undefined,
    },
    {
      label: "Today Return",
      value: analytics.closedCount ? formatNumber(analytics.todayPl, 2) : "Not available",
      tone: analytics.todayPl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
    },
    {
      label: "Weekly Return",
      value: analytics.closedCount ? formatNumber(analytics.weekPl, 2) : "Not available",
      tone: analytics.weekPl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
    },
    {
      label: "Monthly Return",
      value: analytics.closedCount ? formatNumber(analytics.monthPl, 2) : "Not available",
      tone: analytics.monthPl >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
    },
    {
      label: "Total Return (sampled)",
      value:
        totalReturn == null && !analytics.closedCount
          ? "Not available"
          : formatNumber(
              analytics.dailyPl.reduce((s, d) => s + d.pl, 0),
              2,
            ),
    },
    {
      label: "Max Drawdown",
      value:
        analytics.maxDrawdown == null
          ? "Not available"
          : formatNumber(analytics.maxDrawdown, 2),
    },
  ];

  return (
    <section
      className={cn(
        "rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-[var(--space-3)]",
        className,
      )}
      aria-label="Book overview"
    >
      <div className="mb-[var(--space-3)] flex items-end justify-between gap-2">
        <div>
          <p className="qf-label">Portfolio</p>
          <p className="qf-caption mt-0.5">
            Live account · deal-derived returns · never fabricated
          </p>
        </div>
      </div>

      <div className="grid gap-[var(--space-2)] sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {cells.map((c) => (
          <div
            key={c.label}
            className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-[var(--space-2)] py-[var(--space-2)]"
          >
            <p className="text-[9px] font-medium uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
              {c.label}
            </p>
            <p
              className={cn(
                "mt-1 font-mono text-sm tabular-nums tracking-tight text-[var(--fg)]",
                c.tone,
              )}
            >
              {c.value}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-[var(--space-3)] grid gap-[var(--space-3)] lg:grid-cols-2">
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
            Open position allocation
          </p>
          {allocation.length ? (
            <ul className="space-y-1.5">
              {allocation.map((a) => (
                <li
                  key={a.label}
                  className="grid grid-cols-[4.5rem_1fr_3rem] items-center gap-2 text-[11px]"
                >
                  <span className="font-mono text-[var(--fg-muted)]">{a.label}</span>
                  <div className="h-1.5 overflow-hidden rounded-full bg-[var(--bg-elevated)]">
                    <div
                      className="h-full rounded-full bg-[var(--accent)]"
                      style={{ width: `${Math.min(100, a.pct)}%` }}
                    />
                  </div>
                  <span className="text-right font-mono tabular-nums">
                    {formatNumber(a.pct, 1)}%
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[11px] text-[var(--fg-muted)]">
              Not available — no open positions
            </p>
          )}
        </div>
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-[0.08em] text-[var(--fg-subtle)]">
            Exposure notes
          </p>
          <p className="text-[11px] leading-relaxed text-[var(--fg-muted)]">
            Asset allocation and performance use live positions and closed deals only.
            Inception equity for total return is Not available unless provided by the broker
            snapshot.
          </p>
          <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
            Closed trades in sample: {analytics.closedCount || "Not available"}
          </p>
        </div>
      </div>
    </section>
  );
});
