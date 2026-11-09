/**
 * Pure performance helpers with no path-alias imports so Node strip-types
 * unit tests can execute them directly.
 */

export type PerformancePeriod = "today" | "7d" | "30d" | "90d" | "all";

const DAY_MS = 86_400_000;

export const PERFORMANCE_PERIODS: { id: PerformancePeriod; label: string }[] = [
  { id: "today", label: "Today" },
  { id: "7d", label: "7 Days" },
  { id: "30d", label: "30 Days" },
  { id: "90d", label: "90 Days" },
  { id: "all", label: "All Time" },
];

/** UTC day start — matches Overview KPI "Today's P&L" boundary. */
export function startOfUtcDayMs(now = Date.now()): number {
  const d = new Date(now);
  d.setUTCHours(0, 0, 0, 0);
  return d.getTime();
}

export function periodWindowMs(
  period: PerformancePeriod,
  now = Date.now(),
): number | null {
  if (period === "all") return null;
  if (period === "today") return now - startOfUtcDayMs(now);
  if (period === "7d") return 7 * DAY_MS;
  if (period === "30d") return 30 * DAY_MS;
  return 90 * DAY_MS;
}

function finiteOrZero(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : 0;
}

function finiteOrNaN(value: unknown): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : NaN;
}

/** Net P&L including commission/swap/fee when the deal record provides them. */
export function netDealPnl(deal: Record<string, unknown>): number {
  const profit = finiteOrNaN(deal.profit);
  if (!Number.isFinite(profit)) return NaN;
  return (
    profit +
    finiteOrZero(deal.commission) +
    finiteOrZero(deal.swap) +
    finiteOrZero(deal.fee)
  );
}
