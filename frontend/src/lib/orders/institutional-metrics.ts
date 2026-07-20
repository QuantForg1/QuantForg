/** Institutional analytics metrics derived only from live broker trades. */

import type { LiveTrade, TradeAnalytics } from "@/lib/orders/history";
import { computeTradeAnalytics } from "@/lib/orders/history";

export type InstitutionalMetrics = TradeAnalytics & {
  expectancy: number | null;
  kellyPct: number | null;
  calmar: number | null;
  mar: number | null;
  ulcerIndex: number | null;
  sqn: number | null;
  averageMae: number | null;
  averageMfe: number | null;
  maxMae: number | null;
  maxMfe: number | null;
};

/**
 * Compute institutional metrics from closed trades.
 * MAE/MFE require bar-path data — return null (Not available) without fabricating.
 */
export function computeInstitutionalMetrics(
  trades: LiveTrade[],
  opts?: { startingEquity?: number },
): InstitutionalMetrics {
  const base = computeTradeAnalytics(trades, opts);
  const closed = trades.filter((t) => t.status === "closed");
  const wins = closed.filter((t) => t.netPl > 0);
  const losses = closed.filter((t) => t.netPl < 0);
  const n = closed.length;

  const avgWin = wins.length
    ? wins.reduce((s, t) => s + t.netPl, 0) / wins.length
    : 0;
  const avgLossAbs = losses.length
    ? Math.abs(losses.reduce((s, t) => s + t.netPl, 0) / losses.length)
    : 0;
  const winRate = base.winRate;
  const expectancy =
    winRate != null && n > 0
      ? winRate * avgWin - (1 - winRate) * avgLossAbs
      : null;

  // Kelly fraction (simplified): W - (1-W)/(avgWin/avgLoss)
  let kellyPct: number | null = null;
  if (winRate != null && avgLossAbs > 0 && avgWin > 0) {
    const b = avgWin / avgLossAbs;
    const k = winRate - (1 - winRate) / b;
    kellyPct = Number.isFinite(k) ? k * 100 : null;
  }

  const netProfit = closed.reduce((s, t) => s + t.netPl, 0);
  const maxDd = base.maxDrawdown;
  const calmar =
    maxDd != null && maxDd > 0 ? netProfit / maxDd : null;
  const mar = calmar; // same sample when no annualization available

  // Ulcer index from equity curve drawdowns
  let ulcerIndex: number | null = null;
  if (base.equityCurve.length > 1) {
    let peak = base.equityCurve[0]!.equity;
    let sumSq = 0;
    for (const p of base.equityCurve) {
      peak = Math.max(peak, p.equity);
      const ddPct = peak !== 0 ? ((peak - p.equity) / Math.abs(peak)) * 100 : 0;
      sumSq += ddPct * ddPct;
    }
    ulcerIndex = Math.sqrt(sumSq / base.equityCurve.length);
  }

  // System Quality Number (Van Tharp) — R-multiple approx via netPl / avgLoss
  let sqn: number | null = null;
  if (n >= 5 && avgLossAbs > 0) {
    const rMultiples = closed.map((t) => t.netPl / avgLossAbs);
    const mean = rMultiples.reduce((a, b) => a + b, 0) / rMultiples.length;
    const variance =
      rMultiples.reduce((s, r) => s + (r - mean) ** 2, 0) / (rMultiples.length - 1);
    const std = Math.sqrt(variance);
    sqn = std > 0 ? (mean / std) * Math.sqrt(rMultiples.length) : null;
  }

  return {
    ...base,
    expectancy,
    kellyPct,
    calmar,
    mar,
    ulcerIndex,
    sqn,
    // Live MAE/MFE need tick/bar path — never invent
    averageMae: null,
    averageMfe: null,
    maxMae: null,
    maxMfe: null,
  };
}
