"use client";

import { memo, useMemo } from "react";
import Link from "next/link";
import { useTradingSession } from "@/providers/trading-session-provider";
import { num } from "@/lib/desk";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";

/**
 * Compact live risk strip for Terminal — no duplicate full risk desk.
 * Deep analysis lives on /risk-center.
 */
export const QuickRiskSummary = memo(function QuickRiskSummary({
  className,
}: {
  className?: string;
}) {
  const session = useTradingSession();

  const rows = useMemo(() => {
    const equity = num(session.equity);
    const free = num(session.freeMargin);
    const floating = num(session.profit);
    const ddPct =
      Number.isFinite(equity) &&
      equity > 0 &&
      Number.isFinite(floating) &&
      floating < 0
        ? (Math.abs(floating) / equity) * 100
        : Number.isFinite(equity) && equity > 0
          ? 0
          : NaN;

    return [
      {
        label: "Equity",
        value: Number.isFinite(equity) ? formatCurrency(equity) : "—",
      },
      {
        label: "Free",
        value: Number.isFinite(free) ? formatCurrency(free) : "—",
      },
      {
        label: "Float",
        value: Number.isFinite(floating) ? formatCurrency(floating) : "—",
        tone:
          Number.isFinite(floating) && floating < 0
            ? ("danger" as const)
            : Number.isFinite(floating) && floating > 0
              ? ("success" as const)
              : undefined,
      },
      {
        label: "DD",
        value: Number.isFinite(ddPct) ? `${formatNumber(ddPct, 2)}%` : "—",
        tone: ddPct > 2 ? ("danger" as const) : undefined,
      },
    ];
  }, [
    session.equity,
    session.freeMargin,
    session.profit,
  ]);

  return (
    <section
      className={cn(
        "border-t border-[var(--border)] bg-[var(--bg)] px-2.5 py-1.5",
        className,
      )}
      aria-label="Quick risk summary"
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <h2 className="text-[9px] font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">
          Risk
        </h2>
        <Link
          href="/risk-center"
          className="text-[9px] text-[var(--accent)] hover:underline"
        >
          Details
        </Link>
      </div>
      <div className="grid grid-cols-2 gap-x-2 gap-y-1">
        {rows.map((r) => (
          <div key={r.label} className="min-w-0">
            <div className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">
              {r.label}
            </div>
            <div
              className={cn(
                "truncate font-mono text-[10px] tabular text-[var(--fg)]",
                r.tone === "danger" && "text-[var(--danger)]",
                r.tone === "success" && "text-[var(--success)]",
              )}
            >
              {r.value}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
});
