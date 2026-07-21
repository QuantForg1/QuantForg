"use client";

import { memo, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Minus } from "lucide-react";
import { quantAiApi, riskApi, strategyApi } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";
import { useTradingSession } from "@/providers/trading-session-provider";
import { cn, formatNumber } from "@/lib/utils";
import { parseRiskRules } from "@/components/execution/risk-rules-panel";

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
 * Pre-trade AI Decision Card — live data only.
 * Confidence / Reasons from strategy + quant-ai.
 * Risk per trade from Risk Engine only.
 * RR only from ticket entry + SL + TP (never estimated).
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
  const hasTicketGeometry =
    Number.isFinite(entry) && entry > 0 && Number.isFinite(sl) && Number.isFinite(tp);

  const strategyQ = useQuery({
    queryKey: ["ai-decision-strategy", symbol, side, volume, session.connected],
    queryFn: () => strategyApi.evaluate({ symbol, side, volume }),
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

  const riskQ = useQuery({
    queryKey: [
      "ai-decision-risk",
      symbol,
      side,
      volume,
      stopLoss ?? "",
      Number.isFinite(entry) ? entry : "",
      session.connected,
    ],
    queryFn: () =>
      riskApi.check({
        symbol,
        side,
        requested_lots: volume,
        entry_price: Number.isFinite(entry) ? String(entry) : undefined,
        stop_loss_distance: stopLoss || undefined,
        equity: session.equity !== "—" ? session.equity : undefined,
      }),
    enabled: enabled && Boolean(volume.trim()),
    staleTime: 12_000,
    retry: false,
  });

  const card = useMemo(() => {
    const strat = asRecord(strategyQ.data);
    const signal = asRecord(strat.signal);
    const quant = asRecord(quantQ.data);
    const risk = riskQ.data ? asRecord(riskQ.data) : null;
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

    const direction = str(
      signal.direction || quant.trend || strat.decision,
      "",
    ).toUpperCase();
    const displaySide = direction.includes("SELL")
      ? "SELL"
      : direction.includes("BUY")
        ? "BUY"
        : side.toUpperCase();

    // RR — ticket geometry only (never suggested SL/TP)
    let expectedRr: number | null = null;
    if (hasTicketGeometry) {
      const riskDist = Math.abs(entry - sl);
      const rewardDist = Math.abs(tp - entry);
      if (riskDist > 0) expectedRr = rewardDist / riskDist;
    }

    // Risk per trade — Risk Engine only (requires SL so dollar risk is real)
    const hasSl = Boolean(String(stopLoss ?? "").trim());
    const riskPct =
      riskQ.isError || !hasSl ? null : parseRiskEnginePct(risk);
    const riskDecision = risk ? str(risk.decision).toUpperCase() : "";
    const riskSource =
      riskPct != null
        ? `Risk Engine (${riskDecision || "assessed"})`
        : !hasSl
          ? "Requires stop loss"
          : riskQ.isLoading
            ? "Loading Risk Engine…"
            : "Not available";

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
      riskSource,
      expectedHold: null as string | null,
      reasons,
      quantUnavailable,
      loading: strategyQ.isLoading || quantQ.isLoading || riskQ.isLoading,
      error: strategyQ.isError && quantQ.isError,
    };
  }, [
    strategyQ.data,
    strategyQ.isLoading,
    strategyQ.isError,
    quantQ.data,
    quantQ.isLoading,
    quantQ.isError,
    riskQ.data,
    riskQ.isLoading,
    riskQ.isError,
    hasTicketGeometry,
    entry,
    sl,
    tp,
    side,
    stopLoss,
  ]);

  if (!session.connected) {
    return (
      <div
        className={cn(
          "rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5",
          className,
        )}
      >
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          AI Decision Card
        </p>
        <p className="mt-2 text-[11px] text-[var(--fg-muted)]">
          Broker offline — Confidence, Risk, RR, and Reasons are Not available.
        </p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2.5",
        className,
      )}
    >
      <div className="mb-2.5 flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
            AI Decision Card
          </p>
          <p className="mt-0.5 font-[family-name:var(--font-display)] text-lg tracking-tight text-[var(--fg)]">
            {card.displaySide}
          </p>
          <p className="text-[10px] text-[var(--fg-subtle)]">
            Confidence: {card.confidenceSource}
          </p>
        </div>
        <div className="text-right">
          <p className="text-[10px] uppercase tracking-wide text-[var(--fg-subtle)]">
            Confidence
          </p>
          <p
            className={cn(
              "font-mono text-xl tabular-nums",
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

      <div className="mb-2.5 grid grid-cols-3 gap-1.5">
        {(
          [
            [
              "Expected RR",
              card.expectedRr == null
                ? "Not available"
                : `1 : ${formatNumber(card.expectedRr, 2)}`,
              hasTicketGeometry
                ? "Ticket SL/TP"
                : "Requires entry + SL + TP",
            ],
            [
              "Risk / trade",
              card.riskPct == null
                ? "Not available"
                : `${formatNumber(card.riskPct, 2)}%`,
              card.riskSource,
            ],
            ["Expected Hold", "Not available", "Not computed live"],
          ] as const
        ).map(([label, value, hint]) => (
          <div
            key={label}
            className="rounded border border-[var(--border)]/80 bg-[var(--bg)]/40 px-2 py-1.5"
          >
            <p className="text-[9px] uppercase tracking-wide text-[var(--fg-subtle)]">
              {label}
            </p>
            <p className="mt-0.5 font-mono text-[11px] tabular-nums text-[var(--fg)]">
              {value}
            </p>
            <p className="mt-0.5 truncate text-[9px] text-[var(--fg-subtle)]">{hint}</p>
          </div>
        ))}
      </div>

      <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
        Reasons
      </p>
      {card.loading ? (
        <p className="text-[11px] text-[var(--fg-muted)]">Loading live strategy…</p>
      ) : card.error || (!card.reasons.length && card.quantUnavailable) ? (
        <p className="text-[11px] text-[var(--fg-muted)]">Not available</p>
      ) : card.reasons.length ? (
        <ul className="max-h-28 space-y-1 overflow-y-auto">
          {card.reasons.slice(0, 10).map((r) => (
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
