"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  PERFORMANCE_PERIODS,
  computePerformanceWindow,
  type PerformancePeriod,
} from "@/lib/dashboard/performance-window";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "success" | "danger" | "neutral";
}) {
  return (
    <article className="min-w-0 rounded-[var(--radius-os)] border border-[var(--border)] bg-[color-mix(in_srgb,var(--surface)_92%,transparent)] px-3 py-2.5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        {label}
      </p>
      <p
        className={cn(
          "mt-1 truncate font-mono text-sm font-semibold tabular tracking-tight",
          tone === "success" && "text-[var(--success)]",
          tone === "danger" && "text-[var(--danger)]",
          !tone && "text-[var(--fg)]",
        )}
      >
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 truncate text-[11px] text-[var(--fg-muted)]">{hint}</p>
      ) : null}
    </article>
  );
}

function fmtMoney(v: number, currency: string): string {
  return Number.isFinite(v) ? formatCurrency(v, currency) : "—";
}

function fmtPct(v: number): string {
  return Number.isFinite(v) ? `${formatNumber(v * 100, 1)}%` : "—";
}

function fmtRatio(v: number): string {
  return Number.isFinite(v) ? formatNumber(v, 2) : "—";
}

function Spark({ values }: { values: number[] }) {
  if (values.length < 2) {
    return (
      <div className="flex h-16 items-center justify-center rounded-[var(--radius-os)] border border-dashed border-[var(--border)] text-xs text-[var(--fg-muted)]">
        Insufficient equity history
      </div>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1e-9, max - min);
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 100;
      const y = 100 - ((v - min) / span) * 100;
      return `${x},${y}`;
    })
    .join(" ");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg viewBox="0 0 100 100" className="h-16 w-full" preserveAspectRatio="none" aria-hidden>
      <polyline
        fill="none"
        stroke={up ? "var(--success)" : "var(--danger)"}
        strokeWidth="2.5"
        points={pts}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function TradingPerformancePanel({
  deals,
  floatingPnl,
  equity,
  currency = "USD",
  available,
}: {
  deals: Record<string, unknown>[];
  floatingPnl: number;
  equity: number;
  currency?: string;
  available: boolean;
}) {
  const [period, setPeriod] = useState<PerformancePeriod>("30d");
  const stats = useMemo(
    () =>
      computePerformanceWindow(deals, {
        period,
        floatingPnl,
        equity,
      }),
    [deals, period, floatingPnl, equity],
  );

  const code = currency && currency !== "—" ? currency : "USD";

  return (
    <section
      aria-labelledby="trading-performance"
      className="space-y-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-4 shadow-[var(--shadow-card)]"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <h2
            id="trading-performance"
            className="text-sm font-medium text-[var(--fg)]"
          >
            Trading Performance
          </h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Realized vs floating P&amp;L from your account history. Commissions and
            swaps are included when the broker deal record provides them.
          </p>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/journal">Open journal</Link>
        </Button>
      </div>

      <div
        className="flex flex-wrap gap-1"
        role="tablist"
        aria-label="Performance period"
      >
        {PERFORMANCE_PERIODS.map((p) => (
          <button
            key={p.id}
            type="button"
            role="tab"
            aria-selected={period === p.id}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-semibold transition",
              period === p.id
                ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
            )}
            onClick={() => setPeriod(p.id)}
          >
            {p.label}
          </button>
        ))}
      </div>

      {!available ? (
        <p className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-4 text-sm text-[var(--fg-muted)]">
          Performance metrics appear when your broker session and history are
          available.
        </p>
      ) : stats.insufficient ? (
        <p className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--bg)]/40 px-3 py-4 text-sm text-[var(--fg-muted)]">
          Insufficient closed-trade history for this period. Floating P&amp;L is
          still shown when positions are open.
        </p>
      ) : (
        <>
          <Spark values={stats.spark} />
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-5">
            <Metric
              label="Realized P&L"
              value={fmtMoney(stats.realizedPnl, code)}
              tone={
                Number.isFinite(stats.realizedPnl)
                  ? stats.realizedPnl >= 0
                    ? "success"
                    : "danger"
                  : "neutral"
              }
              hint="Closed trades in period"
            />
            <Metric
              label="Floating P&L"
              value={fmtMoney(stats.floatingPnl, code)}
              tone={
                Number.isFinite(stats.floatingPnl)
                  ? stats.floatingPnl >= 0
                    ? "success"
                    : "danger"
                  : "neutral"
              }
              hint="Open positions only"
            />
            <Metric
              label="Period total"
              value={fmtMoney(stats.totalPnl, code)}
              tone={
                Number.isFinite(stats.totalPnl)
                  ? stats.totalPnl >= 0
                    ? "success"
                    : "danger"
                  : "neutral"
              }
            />
            <Metric label="Win rate" value={fmtPct(stats.winRate)} />
            <Metric label="Profit factor" value={fmtRatio(stats.profitFactor)} />
            <Metric
              label="Closed trades"
              value={
                Number.isFinite(stats.closedTrades)
                  ? String(stats.closedTrades)
                  : "—"
              }
            />
            <Metric label="Avg win" value={fmtMoney(stats.averageWin, code)} />
            <Metric
              label="Avg loss"
              value={fmtMoney(stats.averageLoss, code)}
              tone={Number.isFinite(stats.averageLoss) ? "danger" : "neutral"}
            />
            <Metric
              label="Avg reward/risk"
              value={fmtRatio(stats.averageRewardRisk)}
              hint="Only when SL/TP distances exist"
            />
          </div>
        </>
      )}
    </section>
  );
}
