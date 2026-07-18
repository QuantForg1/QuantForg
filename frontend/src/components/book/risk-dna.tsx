"use client";

import { memo, useMemo } from "react";
import { asList, asRecord, num, str } from "@/lib/desk";
import { cn, formatNumber } from "@/lib/utils";
import { BookEmpty } from "@/components/book/empty-state";

type DnaStrand = {
  id: string;
  label: string;
  value: string;
  intensity: number; // 0–1 visual weight
  tone: "ok" | "warn" | "danger" | "neutral";
};

/**
 * Risk DNA — institutional risk fingerprint from portfolio-intelligence + live book.
 * Never invents VaR when backend marks unavailable.
 */
export const RiskDna = memo(function RiskDna({
  intelligence,
  marginLevel,
  freeMargin,
  focused,
  className,
}: {
  intelligence: Record<string, unknown> | null;
  marginLevel: number;
  freeMargin: number;
  focused?: boolean;
  className?: string;
}) {
  const strands = useMemo((): DnaStrand[] => {
    if (!intelligence) return [];
    const risk = asRecord(intelligence.risk);
    const metrics = asRecord(risk.metrics);
    const list: DnaStrand[] = [];

    const varStatus = str(metrics.portfolio_var_status);
    const varVal = num(metrics.portfolio_var);
    if (varStatus === "unavailable" || !Number.isFinite(varVal)) {
      list.push({
        id: "var",
        label: "VaR 95%",
        value: "n/a",
        intensity: 0.15,
        tone: "neutral",
      });
    } else {
      list.push({
        id: "var",
        label: "VaR 95%",
        value: formatNumber(varVal, 2),
        intensity: Math.min(1, Math.abs(varVal) / Math.max(1, num(metrics.exposure, varVal * 10))),
        tone: "warn",
      });
    }

    const esStatus = str(metrics.expected_shortfall_status);
    const esVal = num(metrics.expected_shortfall);
    if (esStatus === "unavailable" || !Number.isFinite(esVal)) {
      list.push({
        id: "es",
        label: "Expected shortfall",
        value: "n/a",
        intensity: 0.15,
        tone: "neutral",
      });
    } else {
      list.push({
        id: "es",
        label: "Expected shortfall",
        value: formatNumber(esVal, 2),
        intensity: Math.min(1, 0.4 + Math.abs(esVal) / Math.max(1, Math.abs(varVal) * 3)),
        tone: "warn",
      });
    }

    const expPct = num(metrics.exposure_pct_equity);
    if (Number.isFinite(expPct)) {
      list.push({
        id: "exp",
        label: "Exposure / equity",
        value: `${formatNumber(expPct, 1)}%`,
        intensity: Math.min(1, expPct / 200),
        tone: expPct > 150 ? "danger" : expPct > 100 ? "warn" : "ok",
      });
    }

    const hhi = num(metrics.concentration_hhi ?? metrics.hhi);
    if (Number.isFinite(hhi)) {
      list.push({
        id: "hhi",
        label: "Concentration",
        value: formatNumber(hhi, 3),
        intensity: Math.min(1, hhi),
        tone: hhi > 0.35 ? "warn" : "ok",
      });
    }

    if (Number.isFinite(marginLevel) && marginLevel > 0) {
      list.push({
        id: "ml",
        label: "Margin level",
        value: `${formatNumber(marginLevel, 0)}%`,
        intensity: marginLevel < 100 ? 1 : marginLevel < 200 ? 0.55 : 0.25,
        tone: marginLevel < 100 ? "danger" : marginLevel < 200 ? "warn" : "ok",
      });
    }

    if (Number.isFinite(freeMargin)) {
      list.push({
        id: "free",
        label: "Free margin",
        value: formatNumber(freeMargin, 0),
        intensity: freeMargin <= 0 ? 1 : 0.3,
        tone: freeMargin <= 0 ? "danger" : "ok",
      });
    }

    const stress = asRecord(intelligence.stress);
    const scenarios = asList(stress.scenarios);
    if (scenarios.length) {
      const worst = scenarios
        .map(asRecord)
        .map((s) => num(s.pnl_impact ?? s.impact ?? s.loss))
        .filter((n) => Number.isFinite(n))
        .sort((a, b) => a - b)[0];
      if (Number.isFinite(worst)) {
        list.push({
          id: "stress",
          label: "Worst stress",
          value: formatNumber(worst, 0),
          intensity: Math.min(1, Math.abs(worst) / 10000),
          tone: worst < 0 ? "danger" : "neutral",
        });
      }
    }

    return list;
  }, [intelligence, marginLevel, freeMargin]);

  return (
    <section
      className={cn(
        "flex h-full min-h-0 flex-col rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        focused && "ring-1 ring-[var(--accent)]",
        className,
      )}
      aria-label="Risk DNA"
    >
      <header className="mb-2 shrink-0">
        <h2 className="qf-label text-[var(--fg)]">Risk DNA</h2>
        <p className="qf-caption">Live risk fingerprint — advisory only</p>
      </header>
      {!intelligence || strands.length === 0 ? (
        <BookEmpty
          title="No risk profile yet"
          description="Connect a session with history so portfolio intelligence can compute VaR and stress."
        />
      ) : (
        <ul className="min-h-0 flex-1 space-y-2 overflow-y-auto">
          {strands.map((s) => (
            <li key={s.id} className="space-y-1">
              <div className="flex items-baseline justify-between gap-2 text-[11px]">
                <span className="text-[var(--fg-muted)]">{s.label}</span>
                <span
                  className={cn(
                    "tabular font-medium",
                    s.tone === "ok" && "text-[var(--success)]",
                    s.tone === "warn" && "text-[var(--warning)]",
                    s.tone === "danger" && "text-[var(--danger)]",
                    s.tone === "neutral" && "text-[var(--fg-subtle)]",
                  )}
                >
                  {s.value}
                </span>
              </div>
              <div
                className="h-1.5 overflow-hidden rounded-full bg-[var(--surface-2)]"
                role="presentation"
              >
                <div
                  className={cn(
                    "h-full rounded-full transition-[width] duration-200",
                    s.tone === "ok" && "bg-[var(--success)]",
                    s.tone === "warn" && "bg-[var(--warning)]",
                    s.tone === "danger" && "bg-[var(--danger)]",
                    s.tone === "neutral" && "bg-[var(--border-strong)]",
                  )}
                  style={{ width: `${Math.round(s.intensity * 100)}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
});
