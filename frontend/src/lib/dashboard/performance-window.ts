/**
 * Account performance windows from persisted deal history + open floating P&L.
 * Never invents metrics — returns NaN / empty when data is insufficient.
 */

import { isTradeDeal } from "./deal-stats";
import { buildEquitySeries, sparkFromSeries, sumPnlInWindow } from "./derive";
import { num, str } from "../desk";
import {
  netDealPnl,
  periodWindowMs,
  type PerformancePeriod,
} from "./performance-math";

export type { PerformancePeriod };
export {
  PERFORMANCE_PERIODS,
  netDealPnl,
  periodWindowMs,
  startOfUtcDayMs,
} from "./performance-math";

function dealTimeMs(deal: Record<string, unknown>): number {
  return Date.parse(str(deal.time ?? deal.close_time ?? deal.deal_time, ""));
}

export type PerformanceWindowStats = {
  period: PerformancePeriod;
  sampleCount: number;
  realizedPnl: number;
  floatingPnl: number;
  totalPnl: number;
  winRate: number;
  profitFactor: number;
  averageWin: number;
  averageLoss: number;
  averageRewardRisk: number;
  closedTrades: number;
  spark: number[];
  insufficient: boolean;
};

export function computePerformanceWindow(
  deals: Record<string, unknown>[],
  opts: {
    period: PerformancePeriod;
    floatingPnl?: number;
    equity?: number;
    now?: number;
  },
): PerformanceWindowStats {
  const now = opts.now ?? Date.now();
  const floating = Number.isFinite(opts.floatingPnl) ? (opts.floatingPnl as number) : 0;
  const windowMs = periodWindowMs(opts.period, now);
  const tradeDeals = deals.filter(isTradeDeal);
  const inWindow = tradeDeals.filter((d) => {
    const t = dealTimeMs(d);
    if (!Number.isFinite(t)) return false;
    if (windowMs == null) return true;
    return now - t <= windowMs;
  });

  const pnls = inWindow
    .map(netDealPnl)
    .filter((p): p is number => Number.isFinite(p));
  const wins = pnls.filter((p) => p > 0);
  const losses = pnls.filter((p) => p < 0);
  const closedTrades = pnls.length;
  const grossProfit = wins.reduce((s, p) => s + p, 0);
  const grossLoss = Math.abs(losses.reduce((s, p) => s + p, 0));
  const realizedPnl =
    windowMs == null
      ? pnls.reduce((s, p) => s + p, 0)
      : sumPnlInWindow(
          inWindow.map((d) => ({ ...d, profit: netDealPnl(d) })),
          windowMs,
          now,
        );

  const rrSamples = inWindow
    .map((d) => {
      const reward = Math.abs(num(d.tp_distance ?? d.reward, NaN));
      const risk = Math.abs(num(d.sl_distance ?? d.risk, NaN));
      if (Number.isFinite(reward) && Number.isFinite(risk) && risk > 0) {
        return reward / risk;
      }
      const p = netDealPnl(d);
      if (!Number.isFinite(p) || p >= 0) return NaN;
      // Cannot infer RR from losing trade alone without distances.
      return NaN;
    })
    .filter((v): v is number => Number.isFinite(v));

  const equity = Number.isFinite(opts.equity) ? (opts.equity as number) : NaN;
  const series =
    Number.isFinite(equity) && inWindow.length
      ? buildEquitySeries(
          inWindow.map((d) => ({ ...d, profit: netDealPnl(d) })),
          equity,
        )
      : [];

  const insufficient = closedTrades === 0 && floating === 0;

  return {
    period: opts.period,
    sampleCount: closedTrades,
    realizedPnl: closedTrades ? realizedPnl : NaN,
    floatingPnl: floating,
    totalPnl:
      closedTrades || floating !== 0
        ? (Number.isFinite(realizedPnl) ? realizedPnl : 0) + floating
        : NaN,
    winRate: closedTrades > 0 ? wins.length / closedTrades : NaN,
    profitFactor: grossLoss > 0 ? grossProfit / grossLoss : NaN,
    averageWin: wins.length ? grossProfit / wins.length : NaN,
    averageLoss: losses.length ? grossLoss / losses.length : NaN,
    averageRewardRisk: rrSamples.length
      ? rrSamples.reduce((s, v) => s + v, 0) / rrSamples.length
      : NaN,
    closedTrades,
    spark: sparkFromSeries(series),
    insufficient,
  };
}
