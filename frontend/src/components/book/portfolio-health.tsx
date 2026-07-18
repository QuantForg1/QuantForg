"use client";

import { memo, useMemo } from "react";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import { num } from "@/lib/desk";

export type PortfolioHealthMetrics = {
  equity: number;
  balance: number;
  freeMargin: number;
  marginLevel: number;
  floating: number;
  positionCount: number;
  exposure: number;
  connected: boolean;
};

/**
 * Portfolio Health — single glance at book viability.
 * Real session/portfolio figures only.
 */
export const PortfolioHealth = memo(function PortfolioHealth({
  metrics,
  focused,
  className,
}: {
  metrics: PortfolioHealthMetrics;
  focused?: boolean;
  className?: string;
}) {
  const healthTone = useMemo(() => {
    if (!metrics.connected) return "neutral" as const;
    if (
      Number.isFinite(metrics.marginLevel) &&
      metrics.marginLevel > 0 &&
      metrics.marginLevel < 100
    ) {
      return "danger" as const;
    }
    if (
      Number.isFinite(metrics.freeMargin) &&
      metrics.freeMargin <= 0 &&
      metrics.connected
    ) {
      return "danger" as const;
    }
    if (metrics.floating < 0 && Math.abs(metrics.floating) > metrics.equity * 0.05) {
      return "warn" as const;
    }
    return "ok" as const;
  }, [metrics]);

  const cells: { label: string; value: string; tone?: string }[] = [
    {
      label: "Equity",
      value: Number.isFinite(metrics.equity) ? formatCurrency(metrics.equity) : "—",
    },
    {
      label: "Balance",
      value: Number.isFinite(metrics.balance) ? formatCurrency(metrics.balance) : "—",
    },
    {
      label: "Free",
      value: Number.isFinite(metrics.freeMargin)
        ? formatCurrency(metrics.freeMargin)
        : "—",
      tone:
        Number.isFinite(metrics.freeMargin) && metrics.freeMargin <= 0
          ? "text-[var(--danger)]"
          : undefined,
    },
    {
      label: "Margin lvl",
      value:
        Number.isFinite(metrics.marginLevel) && metrics.marginLevel > 0
          ? `${formatNumber(metrics.marginLevel, 0)}%`
          : "—",
      tone:
        Number.isFinite(metrics.marginLevel) &&
        metrics.marginLevel > 0 &&
        metrics.marginLevel < 100
          ? "text-[var(--danger)]"
          : undefined,
    },
    {
      label: "Floating",
      value: Number.isFinite(metrics.floating)
        ? formatCurrency(metrics.floating)
        : "—",
      tone:
        metrics.floating >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
    },
    {
      label: "Positions",
      value: String(metrics.positionCount),
    },
    {
      label: "Exposure",
      value: Number.isFinite(metrics.exposure)
        ? formatCurrency(metrics.exposure)
        : "—",
    },
  ];

  return (
    <section
      className={cn(
        "rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Portfolio Health"
    >
      <header className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="qf-label text-[var(--fg)]">Portfolio Health</h2>
        <span
          className={cn(
            "qf-caption tabular",
            healthTone === "ok" && "text-[var(--success)]",
            healthTone === "warn" && "text-[var(--warning)]",
            healthTone === "danger" && "text-[var(--danger)]",
            healthTone === "neutral" && "text-[var(--fg-muted)]",
          )}
        >
          {!metrics.connected
            ? "Offline"
            : healthTone === "ok"
              ? "Stable"
              : healthTone === "warn"
                ? "Stressed"
                : "Critical"}
        </span>
      </header>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {cells.map((c) => (
          <div key={c.label} className="min-w-0">
            <dt className="qf-caption text-[var(--fg-subtle)]">{c.label}</dt>
            <dd
              className={cn(
                "truncate font-mono text-[13px] tabular font-medium text-[var(--fg)]",
                c.tone,
              )}
            >
              {c.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
});

export function exposureFromPositions(positions: Record<string, unknown>[]): number {
  return positions.reduce((sum, p) => {
    const notional = Math.abs(
      num(p.volume, 0) * num(p.current_price ?? p.open_price, 0),
    );
    return sum + (Number.isFinite(notional) ? notional : 0);
  }, 0);
}
