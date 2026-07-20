/**
 * Honest trade stats from MT5 deal history only.
 * Returns NaN when a metric cannot be computed — UI must show "—", never invent.
 */

import { num, str } from "@/lib/desk";
import { sumPnlInWindow } from "@/lib/dashboard/derive";

const DAY_MS = 86_400_000;

export type DealStats = {
  tradeCount: number;
  winRate: number;
  profitFactor: number;
  averageWin: number;
  averageLoss: number;
  todayRealized: number;
  todayProfit: number;
  dailyDrawdown: number;
  dailyDrawdownPct: number;
};

/** Exclude balance/credit/deposit rows from performance samples. */
export function isTradeDeal(deal: Record<string, unknown>): boolean {
  const typ = str(deal.deal_type || deal.type, "").toLowerCase();
  if (
    typ.includes("balance") ||
    typ.includes("credit") ||
    typ.includes("charge") ||
    typ.includes("correction") ||
    typ.includes("bonus") ||
    typ.includes("commission")
  ) {
    return false;
  }
  const symbol = str(deal.symbol, "").trim();
  if (!symbol && typ && !typ.includes("buy") && !typ.includes("sell") && !typ.includes("deal")) {
    return false;
  }
  const profit = num(deal.profit);
  // Keep zero-profit trade rows; drop rows with no parseable profit and no symbol.
  if (!symbol && !Number.isFinite(profit)) return false;
  return true;
}

function startOfLocalDay(now = Date.now()): number {
  const d = new Date(now);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

export function computeDealStats(
  deals: Record<string, unknown>[],
  opts?: {
    floatingProfit?: number;
    equity?: number;
    now?: number;
  },
): DealStats {
  const now = opts?.now ?? Date.now();
  const floating = Number.isFinite(opts?.floatingProfit) ? (opts!.floatingProfit as number) : 0;
  const equity = Number.isFinite(opts?.equity) ? (opts!.equity as number) : NaN;

  const tradeDeals = deals.filter(isTradeDeal);
  const pnls = tradeDeals
    .map((d) => num(d.profit))
    .filter((p): p is number => Number.isFinite(p));

  const wins = pnls.filter((p) => p > 0);
  const losses = pnls.filter((p) => p < 0);
  const n = pnls.length;

  const winRate = n > 0 ? wins.length / n : NaN;
  const grossProfit = wins.reduce((s, p) => s + p, 0);
  const grossLoss = Math.abs(losses.reduce((s, p) => s + p, 0));
  const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : NaN;
  const averageWin = wins.length ? grossProfit / wins.length : NaN;
  const averageLoss = losses.length ? grossLoss / losses.length : NaN;

  const dayStart = startOfLocalDay(now);
  const todayDeals = tradeDeals.filter((d) => {
    const t = Date.parse(str(d.time, ""));
    return Number.isFinite(t) && t >= dayStart;
  });
  const todayPnls = todayDeals
    .map((d) => num(d.profit, 0))
    .filter((p) => Number.isFinite(p));
  const todayRealized = todayPnls.reduce((s, p) => s + p, 0);
  const todayProfit = todayRealized + floating;

  let eq = 0;
  let peak = 0;
  let maxDd = 0;
  for (const p of todayPnls) {
    eq += p;
    peak = Math.max(peak, eq);
    maxDd = Math.max(maxDd, peak - eq);
  }
  if (floating !== 0) {
    eq += floating;
    peak = Math.max(peak, eq);
    maxDd = Math.max(maxDd, peak - eq);
  }

  const dailyDrawdown = todayPnls.length || floating !== 0 ? maxDd : NaN;
  const dailyDrawdownPct =
    Number.isFinite(dailyDrawdown) && Number.isFinite(equity) && equity > 0
      ? (dailyDrawdown / equity) * 100
      : NaN;

  return {
    tradeCount: n,
    winRate,
    profitFactor,
    averageWin,
    averageLoss,
    todayRealized,
    todayProfit,
    dailyDrawdown,
    dailyDrawdownPct,
  };
}

/** Realized PnL in the last 24h from trade deals only. */
export function realizedLast24h(deals: Record<string, unknown>[], now = Date.now()): number {
  return sumPnlInWindow(deals.filter(isTradeDeal), DAY_MS, now);
}
