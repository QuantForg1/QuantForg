/** Live candle updates from a stream of last prices (pure; unit-tested). */

export type Bar = { time: number; open: number; high: number; low: number; close: number; volume?: number };

export const TIMEFRAME_SECONDS: Record<string, number> = {
  M1: 60,
  M5: 300,
  M15: 900,
  M30: 1800,
  H1: 3600,
  H4: 14400,
  D1: 86400,
  W1: 604800,
};

/**
 * Broker candle clocks are often UTC+2/+3 rather than UTC. Estimate the
 * offset (seconds, multiple of 30 min) from the newest bar while the market
 * is live; 0 when the last bar is too old to tell (closed market).
 */
export function clockOffsetSeconds(lastBarTime: number, nowSec: number, tfSec: number): number {
  const currentBar = Math.floor(nowSec / tfSec) * tfSec;
  const diff = lastBarTime - currentBar;
  if (Math.abs(diff) > 14 * 3600) return 0;
  const half = 1800;
  const rounded = Math.round(diff / half) * half;
  // A lag of one bar on short timeframes is normal, not an offset.
  return Math.abs(rounded) < Math.max(tfSec, half) ? 0 : rounded;
}

/**
 * Apply a live price at wall-clock `nowSec`. Returns the bar to send to the
 * chart (updated or newly opened) and whether it is new, or null when the
 * price cannot be placed (no history, non-finite, or older than the last bar).
 */
export function applyLivePrice(
  bars: Bar[],
  price: number,
  nowSec: number,
  tfSec: number,
  offsetSec: number,
): { bar: Bar; isNew: boolean } | null {
  if (!bars.length || !Number.isFinite(price) || price <= 0 || !tfSec) return null;
  const last = bars[bars.length - 1];
  const barTime = Math.floor((nowSec + offsetSec) / tfSec) * tfSec;
  if (barTime < last.time) return null;
  if (barTime === last.time) {
    const bar = { ...last, close: price, high: Math.max(last.high, price), low: Math.min(last.low, price) };
    bars[bars.length - 1] = bar;
    return { bar, isNew: false };
  }
  // Do not invent a bar across a long gap (closed market, stale feed).
  if (barTime - last.time > tfSec * 3) return null;
  const open = last.close;
  const bar = { time: barTime, open, high: Math.max(open, price), low: Math.min(open, price), close: price, volume: 0 };
  bars.push(bar);
  return { bar, isNew: true };
}
