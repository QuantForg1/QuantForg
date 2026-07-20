"use client";

import { memo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Minus } from "lucide-react";
import { quantAiApi, strategyApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";

const NA = "Not available";

/**
 * Strategy Intelligence — explain trades only from live strategy / quant-ai.
 * Structure tags (OB/FVG/etc.) appear only when returned by APIs.
 */
export const StrategyIntelligencePanel = memo(function StrategyIntelligencePanel({
  symbol,
  className,
}: {
  symbol: string;
  className?: string;
}) {
  const session = useTradingSession();
  const enabled = session.connected && Boolean(symbol.trim());

  const strategyQ = useQuery({
    queryKey: ["strategy-intel", symbol],
    queryFn: () => strategyApi.evaluate({ symbol, side: "buy", volume: "0.01" }),
    enabled,
    staleTime: 30_000,
    retry: false,
  });

  const quantQ = useQuery({
    queryKey: ["quant-intel", symbol],
    queryFn: () => quantAiApi.symbol(symbol),
    enabled,
    staleTime: 30_000,
    retry: false,
  });

  const strat = asRecord(strategyQ.data);
  const signal = asRecord(strat.signal);
  const quant = asRecord(quantQ.data);
  const pre = asRecord(strat.preconditions);

  const confidence = (() => {
    const q = num(quant.confidence_pct, NaN);
    if (Number.isFinite(q)) return q <= 1 ? q * 100 : q;
    const c = num(quant.confidence, NaN);
    if (Number.isFinite(c)) return c <= 1 ? c * 100 : c;
    const s = num(signal.confidence, NaN);
    if (Number.isFinite(s)) return s <= 1 ? s * 100 : s;
    return null;
  })();

  const rows: { label: string; value: string; ok?: boolean }[] = [
    { label: "Why opened", value: str(signal.direction || quant.trend, NA) },
    { label: "Why closed", value: NA },
    {
      label: "Risk",
      value: str(strat.risk_decision || asRecord(strat.risk).allowed, NA),
    },
    {
      label: "Confidence",
      value: confidence == null ? NA : `${formatNumber(confidence, 0)}%`,
    },
    { label: "Confluence", value: NA },
    { label: "Trend", value: str(quant.trend || signal.direction, NA) },
    { label: "Liquidity", value: str(pre.liquidity ?? pre.has_liquidity, NA) },
    { label: "Order Block", value: str(pre.order_block ?? pre.has_order_block, NA) },
    { label: "FVG", value: str(pre.fvg ?? pre.has_fvg, NA) },
    {
      label: "Market Structure",
      value: str(pre.structure ?? pre.has_structure ?? quant.structure, NA),
    },
    { label: "Session", value: str(pre.session ?? quant.session, NA) },
    { label: "News", value: NA },
  ];

  const reasons = [
    ...asList(signal.reasons).map(String),
    ...asList(quant.reasons).map(String),
  ].filter(Boolean);

  if (!session.connected) {
    return (
      <div className={cn("rounded-lg border border-[var(--border)] p-3", className)}>
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Strategy Intelligence
        </p>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Broker offline — {NA}
        </p>
      </div>
    );
  }

  return (
    <div className={cn("rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-3", className)}>
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
        Strategy Intelligence
      </p>
      <p className="mt-1 text-[11px] text-[var(--fg-muted)]">
        Live strategy / quant-ai only · never fabricated structure tags
      </p>

      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        {rows.map((r) => (
          <div key={r.label}>
            <dt className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">
              {r.label}
            </dt>
            <dd className="font-mono text-[11px] text-[var(--fg)]">
              {r.value === "" || r.value === "undefined" ? NA : String(r.value)}
            </dd>
          </div>
        ))}
      </dl>

      <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        AI reasoning
      </p>
      {strategyQ.isLoading || quantQ.isLoading ? (
        <p className="mt-1 text-[11px] text-[var(--fg-muted)]">Loading…</p>
      ) : reasons.length ? (
        <ul className="mt-1 max-h-40 space-y-1 overflow-y-auto">
          {reasons.slice(0, 16).map((label) => (
            <li key={label} className="flex items-start gap-1.5 text-[11px]">
              <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" />
              <span>{label}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 flex items-center gap-1.5 text-[11px] text-[var(--fg-muted)]">
          <Minus className="h-3.5 w-3.5" />
          {NA}
        </p>
      )}
    </div>
  );
});
