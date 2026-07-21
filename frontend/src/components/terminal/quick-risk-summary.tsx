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
    const used =
      Number.isFinite(equity) && Number.isFinite(free)
        ? Math.max(0, equity - free)
        : NaN;
    const marginPct =
      Number.isFinite(equity) && equity > 0 && Number.isFinite(used)
        ? (used / equity) * 100
        : NaN;
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
        label: "Free margin",
        value: Number.isFinite(free) ? formatCurrency(free) : "—",
      },
      {
        label: "Margin used",
        value: Number.isFinite(used) ? formatCurrency(used) : "—",
        hint: Number.isFinite(marginPct)
          ? `${formatNumber(marginPct, 1)}%`
          : undefined,
      },
      {
        label: "Open risk",
        value: Number.isFinite(floating) ? formatCurrency(floating) : "—",
        tone:
          Number.isFinite(floating) && floating < 0
            ? ("danger" as const)
            : Number.isFinite(floating) && floating > 0
              ? ("success" as const)
              : undefined,
      },
      {
        label: "Float DD",
        value: Number.isFinite(ddPct) ? `${formatNumber(ddPct, 2)}%` : "—",
        tone: ddPct > 2 ? ("danger" as const) : undefined,
      },
      {
        label: "Positions",
        value: String(session.positions.length),
      },
    ];
  }, [
    session.equity,
    session.freeMargin,
    session.profit,
    session.positions.length,
  ]);

  return (
    <section
      className={cn(
        "border-t border-[var(--border)] bg-[var(--bg)] px-3 py-2",
        className,
      )}
      aria-label="Quick risk summary"
    >
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <h2 className="text-[10px] font-semibold uppercase tracking-wide text-[var(--fg-subtle)]">
          Quick risk
        </h2>
        <Link
          href="/risk-center"
          className="text-[10px] text-[var(--accent)] hover:underline"
        >
          Risk Center
        </Link>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
        {rows.map((r) => (
          <div key={r.label} className="min-w-0">
            <div className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">
              {r.label}
            </div>
            <div
              className={cn(
                "truncate font-mono text-[11px] tabular text-[var(--fg)]",
                r.tone === "danger" && "text-[var(--danger)]",
                r.tone === "success" && "text-[var(--success)]",
              )}
            >
              {r.value}
              {r.hint ? (
                <span className="ml-1 text-[var(--fg-subtle)]">{r.hint}</span>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
});
