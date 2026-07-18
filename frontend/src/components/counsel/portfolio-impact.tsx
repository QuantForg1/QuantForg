"use client";

import { memo, useMemo } from "react";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatCurrency, formatNumber } from "@/lib/utils";
import { CounselEmpty } from "@/components/counsel/empty-state";

/**
 * Portfolio Impact — how a decision sits against the live book.
 * Session + Quant AI portfolio/risk modules only.
 */
export const PortfolioImpact = memo(function PortfolioImpact({
  equity,
  freeMargin,
  floating,
  positionCount,
  quantModules,
  focused,
  className,
}: {
  equity: number;
  freeMargin: number;
  floating: number;
  positionCount: number;
  quantModules: Record<string, unknown> | null;
  focused?: boolean;
  className?: string;
}) {
  const lines = useMemo(() => {
    const next: { label: string; value: string }[] = [
      {
        label: "Equity",
        value: Number.isFinite(equity) ? formatCurrency(equity) : "—",
      },
      {
        label: "Free margin",
        value: Number.isFinite(freeMargin) ? formatCurrency(freeMargin) : "—",
      },
      {
        label: "Floating",
        value: Number.isFinite(floating) ? formatCurrency(floating) : "—",
      },
      { label: "Open positions", value: String(positionCount) },
    ];

    if (quantModules) {
      const portfolio = asRecord(quantModules.portfolio);
      const risk = asRecord(quantModules.risk);
      const corr = asRecord(quantModules.correlation);
      if (str(portfolio.summary ?? portfolio.status)) {
        next.push({
          label: "QA portfolio",
          value: str(portfolio.summary ?? portfolio.status).slice(0, 80),
        });
      }
      const heat = num(risk.heat ?? risk.portfolio_heat ?? risk.score);
      if (Number.isFinite(heat)) {
        next.push({ label: "Risk heat", value: formatNumber(heat, 2) });
      }
      const warnings = asList(risk.warnings ?? corr.warnings)
        .map((v) => str(v))
        .filter(Boolean);
      if (warnings[0]) {
        next.push({ label: "Warning", value: warnings[0].slice(0, 80) });
      }
    }

    return next;
  }, [equity, freeMargin, floating, positionCount, quantModules]);

  const hasBook =
    Number.isFinite(equity) || positionCount > 0 || quantModules != null;

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Portfolio Impact"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Portfolio Impact</h2>
        <p className="qf-caption">Live book · never invents exposure</p>
      </header>
      {!hasBook ? (
        <CounselEmpty
          title="No book context"
          description="Attach a session so Counsel can relate decisions to real equity and risk."
        />
      ) : (
        <dl className="min-h-0 flex-1 space-y-1.5 overflow-y-auto text-[11px]">
          {lines.map((l) => (
            <div
              key={l.label}
              className="flex justify-between gap-3 border-b border-[var(--border)] py-1"
            >
              <dt className="text-[var(--fg-subtle)]">{l.label}</dt>
              <dd className="text-right tabular text-[var(--fg)]">{l.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
});
