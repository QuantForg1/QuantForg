"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Minus } from "lucide-react";
import { quantAiApi, riskApi, strategyApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";
import { parseRiskRules } from "@/components/execution/risk-rules-panel";
import { stopLossDistance } from "@/lib/execution/position-sizing";

type Props = {
  symbol: string;
  side: "buy" | "sell";
  volume: string;
  entryPrice?: number;
  stopLoss?: string;
  takeProfit?: string;
  className?: string;
};

function parseRiskEnginePct(risk: Record<string, unknown> | null): number | null {
  if (!risk) return null;
  const rules = parseRiskRules(risk);
  const maxRisk = rules.find((r) => r.id === "max_risk" || /risk per trade/i.test(r.name));
  if (maxRisk) {
    const m = maxRisk.current.replace(/%/g, "").trim();
    const v = Number(m);
    if (Number.isFinite(v)) return v;
  }
  const direct = num(risk.risk_per_trade_pct ?? risk.risk_pct, NaN);
  return Number.isFinite(direct) ? direct : null;
}

/**
 * Pre-trade AI Decision Card — live metrics only.
 * Unavailable fields are hidden (never repeated "Not available").
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
  const entry = Number.isFinite(entryPrice) ? Number(entryPrice) : NaN;
  const sl = num(stopLoss, NaN);
  const tp = num(takeProfit, NaN);
  const slDistance = stopLossDistance(entry, sl);
  const hasTicketGeometry =
    Number.isFinite(entry) &&
    entry > 0 &&
    Number.isFinite(sl) &&
    Number.isFinite(tp) &&
    slDistance != null;

  const strategyQ = useQuery({
    queryKey: ["ai-decision-strategy", symbol, side, session.connected],
    queryFn: () => strategyApi.evaluate({ symbol, side, volume }),
    enabled,
    staleTime: 45_000,
    refetchOnWindowFocus: false,
    retry: false,
  });

  const quantQ = useQuery({
    queryKey: ["ai-decision-quant", symbol, session.connected],
    queryFn: () => quantAiApi.symbol(symbol),
    enabled,
    staleTime: 45_000,
    refetchOnWindowFocus: false,
    retry: false,
  });

  const riskQ = useQuery({
    queryKey: [
      "ai-decision-risk",
      symbol,
      side,
      volume,
      slDistance ?? "",
      Number.isFinite(entry) ? entry : "",
      session.connected,
    ],
    queryFn: () =>
      riskApi.check({
        symbol,
        side,
        requested_lots: volume,
        entry_price: Number.isFinite(entry) ? String(entry) : undefined,
        stop_loss_distance: slDistance != null ? String(slDistance) : undefined,
        sizing_method: "percentage_risk",
        equity: session.equity !== "—" ? session.equity : undefined,
      }),
    enabled: enabled && Boolean(volume.trim()) && slDistance != null,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    retry: false,
  });

  const card = useMemo(() => {
    const strat = asRecord(strategyQ.data);
    const signal = asRecord(strat.signal);
    const quant = asRecord(quantQ.data);
    const risk = riskQ.data ? asRecord(riskQ.data) : null;

    const stratConf = num(signal.confidence, NaN);
    const quantConfPct = num(quant.confidence_pct, NaN);
    const quantConf = num(quant.confidence, NaN);
    let confidencePct: number | null = null;
    let confidenceSource = "";
    if (Number.isFinite(quantConfPct)) {
      confidencePct = quantConfPct <= 1 ? quantConfPct * 100 : quantConfPct;
      confidenceSource = "quant-ai";
    } else if (Number.isFinite(quantConf)) {
      confidencePct = quantConf <= 1 ? quantConf * 100 : quantConf;
      confidenceSource = "quant-ai";
    } else if (Number.isFinite(stratConf)) {
      confidencePct = stratConf <= 1 ? stratConf * 100 : stratConf;
      confidenceSource = "strategy";
    }

    const direction = str(
      signal.direction || quant.trend || strat.decision,
      "",
    ).toUpperCase();
    const displaySide = direction.includes("SELL")
      ? "SELL"
      : direction.includes("BUY")
        ? "BUY"
        : side.toUpperCase();

    let expectedRr: number | null = null;
    if (hasTicketGeometry) {
      const riskDist = Math.abs(entry - sl);
      const rewardDist = Math.abs(tp - entry);
      if (riskDist > 0) expectedRr = rewardDist / riskDist;
    }

    const riskPct =
      riskQ.isError || slDistance == null ? null : parseRiskEnginePct(risk);
    const riskDecision = risk ? str(risk.decision).toUpperCase() : "";

    const reasons: { ok: boolean; label: string }[] = [];
    const signalReasons = asList(signal.reasons)
      .map((r) => String(r).trim())
      .filter(Boolean);
    const quantReasons = asList(quant.reasons)
      .map((r) => String(r).trim())
      .filter(Boolean);
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
      riskDecision,
      reasons,
      loading: strategyQ.isLoading || quantQ.isLoading,
    };
  }, [
    strategyQ.data,
    strategyQ.isLoading,
    quantQ.data,
    quantQ.isLoading,
    riskQ.data,
    riskQ.isError,
    hasTicketGeometry,
    entry,
    sl,
    tp,
    side,
    slDistance,
  ]);

  if (!session.connected) return null;

  const metricTiles: { label: string; value: string; hint?: string }[] = [];
  if (card.expectedRr != null) {
    metricTiles.push({
      label: "Risk / Reward",
      value: `1 : ${formatNumber(card.expectedRr, 2)}`,
      hint: "Ticket SL/TP",
    });
  }
  if (card.riskPct != null) {
    metricTiles.push({
      label: "Risk / trade",
      value: `${formatNumber(card.riskPct, 2)}%`,
      hint: card.riskDecision
        ? `Risk Engine · ${card.riskDecision}`
        : "Risk Engine",
    });
  }

  return (
    <div
      className={cn(
        "rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-2",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[9px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            AI Decision
          </p>
          <p className="mt-0.5 font-[family-name:var(--font-display)] text-base tracking-tight text-[var(--fg)]">
            {card.displaySide}
          </p>
        </div>
        {card.confidencePct != null ? (
          <div className="text-right">
            <p className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">
              Confidence
            </p>
            <p
              className={cn(
                "font-mono text-lg tabular-nums",
                card.confidencePct >= 70
                  ? "text-[var(--success)]"
                  : card.confidencePct >= 50
                    ? "text-[var(--warning)]"
                    : "text-[var(--fg)]",
              )}
            >
              {formatNumber(card.confidencePct, 0)}%
            </p>
            {card.confidenceSource ? (
              <p className="text-[9px] text-[var(--fg-subtle)]">{card.confidenceSource}</p>
            ) : null}
          </div>
        ) : null}
      </div>

      {metricTiles.length > 0 ? (
        <div
          className={cn(
            "mt-2 grid gap-1.5",
            metricTiles.length > 1 ? "grid-cols-2" : "grid-cols-1",
          )}
        >
          {metricTiles.map((t) => (
            <div
              key={t.label}
              className="rounded border border-[var(--border)]/80 bg-[var(--bg)]/40 px-2 py-1.5"
            >
              <p className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">
                {t.label}
              </p>
              <p className="mt-0.5 font-mono text-[11px] tabular-nums text-[var(--fg)]">
                {t.value}
              </p>
              {t.hint ? (
                <p className="mt-0.5 truncate text-[9px] text-[var(--fg-subtle)]">{t.hint}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      {card.loading ? (
        <p className="mt-2 text-[10px] text-[var(--fg-muted)]">Loading strategy…</p>
      ) : card.reasons.length > 0 ? (
        <>
          <p className="mb-1 mt-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
            Reasons
          </p>
          <ul className="max-h-24 space-y-1 overflow-y-auto">
            {card.reasons.slice(0, 8).map((r) => (
              <li key={r.label} className="flex items-start gap-1.5 text-[11px]">
                {r.ok ? (
                  <Check className="mt-0.5 h-3 w-3 shrink-0 text-[var(--success)]" />
                ) : (
                  <Minus className="mt-0.5 h-3 w-3 shrink-0 text-[var(--fg-subtle)]" />
                )}
                <span className={r.ok ? "text-[var(--fg)]" : "text-[var(--fg-muted)]"}>
                  {r.label}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </div>
  );
});
