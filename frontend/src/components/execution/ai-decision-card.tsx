"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Minus } from "lucide-react";
import { quantAiApi, strategyApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";

type Props = {
  symbol: string;
  side: "buy" | "sell";
  volume: string;
  entryPrice?: number;
  stopLoss?: string;
  takeProfit?: string;
  className?: string;
};

/**
 * Pre-trade AI Decision Card — live strategy / quant-ai only.
 * Never invents confidence, RR, hold time, or structure reasons.
 */
export const AiDecisionCard = memo(function AiDecisionCard({
  symbol,
  side,
  volume,
  entryPrice,
  stopLoss,
  takeProfit,
  className,
}: Props) {
  const session = useTradingSession();
  const enabled = session.connected && Boolean(symbol.trim());

  const strategyQ = useQuery({
    queryKey: ["ai-decision-strategy", symbol, side, session.connected],
    queryFn: () =>
      strategyApi.evaluate({
        symbol,
        side,
        volume,
      }),
    enabled,
    staleTime: 20_000,
    retry: false,
  });

  const quantQ = useQuery({
    queryKey: ["ai-decision-quant", symbol, session.connected],
    queryFn: () => quantAiApi.symbol(symbol),
    enabled,
    staleTime: 20_000,
    retry: false,
  });

  const card = useMemo(() => {
    const strat = asRecord(strategyQ.data);
    const signal = asRecord(strat.signal);
    const quant = asRecord(quantQ.data);
    const quantUnavailable =
      str(quant.status).toLowerCase() === "unavailable" || !quantQ.data;

    const stratConf = num(signal.confidence, NaN);
    const quantConfPct = num(quant.confidence_pct, NaN);
    const quantConf = num(quant.confidence, NaN);
    let confidencePct: number | null = null;
    let confidenceSource = "Not available";
    if (Number.isFinite(quantConfPct)) {
      confidencePct = quantConfPct <= 1 ? quantConfPct * 100 : quantConfPct;
      confidenceSource = "quant-ai / live candles";
    } else if (Number.isFinite(quantConf)) {
      confidencePct = quantConf <= 1 ? quantConf * 100 : quantConf;
      confidenceSource = "quant-ai / live candles";
    } else if (Number.isFinite(stratConf)) {
      confidencePct = stratConf <= 1 ? stratConf * 100 : stratConf;
      confidenceSource = "strategy evaluate";
    }

    const direction = str(signal.direction || quant.trend || strat.decision, "").toUpperCase();
    const displaySide = direction.includes("SELL")
      ? "SELL"
      : direction.includes("BUY")
        ? "BUY"
        : side.toUpperCase();

    const entry = Number.isFinite(entryPrice) ? Number(entryPrice) : NaN;
    const sl = num(stopLoss, NaN);
    const tp = num(takeProfit, NaN);
    const sugSl = num(quant.suggested_stop, NaN);
    const sugTp = num(quant.suggested_tp, NaN);
    const useSl = Number.isFinite(sl) ? sl : sugSl;
    const useTp = Number.isFinite(tp) ? tp : sugTp;

    let expectedRr: number | null = null;
    let riskPct: number | null = null;
    const equity = num(session.equity, NaN);
    const vol = num(volume, NaN);
    if (Number.isFinite(entry) && Number.isFinite(useSl) && Number.isFinite(useTp) && entry > 0) {
      const riskDist = Math.abs(entry - useSl);
      const rewardDist = Math.abs(useTp - entry);
      if (riskDist > 0) expectedRr = rewardDist / riskDist;
      // Approx gold risk %: volume * |entry-sl| * contract(100) / equity * 100
      if (Number.isFinite(equity) && equity > 0 && Number.isFinite(vol)) {
        const dollarRisk = vol * riskDist * 100;
        riskPct = (dollarRisk / equity) * 100;
      }
    }

    const reasons: { ok: boolean; label: string }[] = [];
    const signalReasons = asList(signal.reasons).map((r) => String(r).trim()).filter(Boolean);
    const quantReasons = asList(quant.reasons).map((r) => String(r).trim()).filter(Boolean);
    const preconditions = asRecord(strat.preconditions);
    for (const [k, v] of Object.entries(preconditions)) {
      if (typeof v === "boolean") {
        reasons.push({ ok: v, label: k.replace(/_/g, " ") });
      }
    }
    for (const label of [...signalReasons, ...quantReasons]) {
      if (!reasons.some((r) => r.label.toLowerCase() === label.toLowerCase())) {
        reasons.push({ ok: true, label });
      }
    }

    return {
      displaySide,
      confidencePct,
      confidenceSource,
      expectedRr,
      riskPct,
      expectedHold: null as string | null,
      reasons,
      quantUnavailable,
      loading: strategyQ.isLoading || quantQ.isLoading,
      error: strategyQ.isError && quantQ.isError,
    };
  }, [
    strategyQ.data,
    strategyQ.isLoading,
    strategyQ.isError,
    quantQ.data,
    quantQ.isLoading,
    quantQ.isError,
    entryPrice,
    stopLoss,
    takeProfit,
    side,
    volume,
    session.equity,
  ]);

  if (!session.connected) {
    return (
      <div
        className={cn(
          "rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3",
          className,
        )}
      >
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          AI Decision Card
        </p>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Broker offline — live strategy confidence is Not available.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3",
        className,
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            AI Decision Card
          </p>
          <p className="mt-1 font-[family-name:var(--font-display)] text-xl tracking-tight text-[var(--fg)]">
            {card.displaySide}
          </p>
          <p className="text-[10px] text-[var(--fg-subtle)]">
            Source: {card.confidenceSource}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">Confidence</p>
          <p
            className={cn(
              "font-mono text-2xl tabular-nums",
              card.confidencePct != null && card.confidencePct >= 70
                ? "text-[var(--success)]"
                : card.confidencePct != null && card.confidencePct >= 50
                  ? "text-[var(--warning)]"
                  : "text-[var(--fg)]",
            )}
          >
            {card.confidencePct == null
              ? "Not available"
              : `${formatNumber(card.confidencePct, 0)}%`}
          </p>
        </div>
      </div>

      <div className="mb-3 grid grid-cols-3 gap-2">
        {(
          [
            [
              "Expected RR",
              card.expectedRr == null ? "Not available" : `1 : ${formatNumber(card.expectedRr, 2)}`,
            ],
            [
              "Risk",
              card.riskPct == null ? "Not available" : `${formatNumber(card.riskPct, 2)}%`,
            ],
            ["Expected Hold", card.expectedHold ?? "Not available"],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="rounded border border-[var(--border)]/80 bg-[var(--bg)]/40 px-2 py-1.5">
            <p className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">{label}</p>
            <p className="mt-0.5 font-mono text-[11px] tabular-nums text-[var(--fg)]">{value}</p>
          </div>
        ))}
      </div>

      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        Reasons
      </p>
      {card.loading ? (
        <p className="text-[11px] text-[var(--fg-muted)]">Loading live strategy…</p>
      ) : card.error || (!card.reasons.length && card.quantUnavailable) ? (
        <p className="text-[11px] text-[var(--fg-muted)]">Not available</p>
      ) : card.reasons.length ? (
        <ul className="max-h-36 space-y-1 overflow-y-auto">
          {card.reasons.slice(0, 12).map((r) => (
            <li key={r.label} className="flex items-start gap-1.5 text-[11px]">
              {r.ok ? (
                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--success)]" />
              ) : (
                <Minus className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--fg-subtle)]" />
              )}
              <span className={r.ok ? "text-[var(--fg)]" : "text-[var(--fg-muted)]"}>
                {r.label}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[11px] text-[var(--fg-muted)]">Not available</p>
      )}
    </div>
  );
});
