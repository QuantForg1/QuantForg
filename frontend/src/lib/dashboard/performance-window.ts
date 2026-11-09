/**
 * Account performance windows from persisted deal history + open floating P&L.
 * Never invents metrics — returns NaN / empty when data is insufficient.
 */

import { isTradeDeal } from "@/lib/dashboard/deal-stats";
import { buildEquitySeries, sparkFromSeries, sumPnlInWindow } from "@/lib/dashboard/derive";
import { num, str } from "@/lib/desk";

export type PerformancePeriod = "today" | "7d" | "30d" | "90d" | "all";

const DAY_MS = 86_400_000;

export const PERFORMANCE_PERIODS: { id: PerformancePeriod; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "7d", label: "7 Days" },
  { id: "30d", label: "30 Days" },
  { id: "90d", label: "90 Days" },
  { id: "all", label: "All Time" },
];

export function periodWindowMs(period: PerformancePeriod, now = Date.now()): number | null {
  if (period === "all") return null;
  if (period === "today") {
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    return now - d.getTime();
  }
  if (period === "7d") return 7 * DAY_MS;
  if (period === "30d") return 30 * DAY_MS;
  return 90 * DAY_MS;
}

function dealTimeMs(deal: Record<string, unknown>): number {
  return Date.parse(str(deal.time ?? deal.close_time ?? deal.deal_time, ""));
}

function netDealPnl(deal: Record<string, unknown>): number {
  const profit = num(deal.profit);
  if (!Number.isFinite(profit)) return NaN;
  const commission = num(deal.commission, 0);
  const swap = num(deal.swap, 0);
  const fee = num(deal.fee, 0);
  return (
    profit +
    (Number.isFinite(commission) ? commission : 0) +
    (Number.isFinite(swap) ? swap : 0) +
    (Number.isFinite(fee) ? fee : 0)
  );
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
