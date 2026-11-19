/**
 * Display-only XAUUSD intelligence for the Overview panel.
 *
 * This module never feeds orders, robot logic, stops, or risk.
 *
 * Closed candles
 * A candle is confirmed only after its timeframe has elapsed. The forming
 * bar is excluded from support, resistance, regime, and momentum.
 *
 * Support and resistance
 * A swing low is a confirmed low strictly below the `wing` bars on each
 * side. A swing high is the same test on highs. Support is the nearest
 * swing lows below the reference price (at most two). Resistance is the
 * nearest swing highs above it. No level is invented when a pivot is absent.
 *
 * Regime, over the last 48 confirmed bars (minimum 24):
 * - recent volatility: mean true range of the last 14 bars
 * - baseline: median true range of the window
 * - efficiency: absolute net close change divided by the sum of absolute
 *   close changes over the last 20 closes
 * High Volatility when recent range is at least 1.75× the baseline.
 * Low Volatility when it is at most 0.55× the baseline.
 * Trending when efficiency is at least 0.5.
 * Otherwise Ranging.
 *
 * Momentum uses the last 10 confirmed closes against the recent true range:
 * Strong above 1.5×, Moderate above 0.6×, otherwise Weak.
 *
 * Direction uses a 20-bar average and the close from 10 bars earlier.
 * A research BUY or SELL overrides that read. WAIT does not.
 *
 * Sessions are fixed UTC windows and are not adjusted for daylight saving:
 * Asian 00:00–09:00, London 07:00–16:00, New York 12:00–21:00.
 * Overlaps are named before the single session.
 */

export type DisplayCandle = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type MarketRegime =
  | "Trending"
  | "Ranging"
  | "High Volatility"
  | "Low Volatility";

export type MarketMomentum = "Strong" | "Moderate" | "Weak";

export type MarketDirection = "Bullish" | "Bearish" | "Neutral";

const TIMEFRAME_SECONDS: Record<string, number> = {
  M1: 60,
  M5: 300,
  M15: 900,
  M30: 1800,
  H1: 3600,
  H4: 14400,
  D1: 86400,
  W1: 604800,
};

const WING = 2;
const MIN_BARS = 24;

export function timeframeSeconds(timeframe: string): number {
  return TIMEFRAME_SECONDS[timeframe] ?? TIMEFRAME_SECONDS.M15;
}

export function confirmedCandles(
  candles: DisplayCandle[],
  timeframe: string,
  nowSec: number,
): DisplayCandle[] {
  const duration = timeframeSeconds(timeframe);
  return candles
    .filter(
      (candle) =>
        Number.isFinite(candle.time) &&
        [candle.open, candle.high, candle.low, candle.close].every(Number.isFinite) &&
        candle.high >= candle.low &&
        candle.time + duration <= nowSec,
    )
    .sort((a, b) => a.time - b.time);
}

function swings(
  candles: DisplayCandle[],
  field: "high" | "low",
): number[] {
  const levels: number[] = [];
  for (let i = WING; i < candles.length - WING; i += 1) {
    const value = candles[i][field];
    let pivot = true;
    for (let j = 1; j <= WING; j += 1) {
      const left = candles[i - j][field];
      const right = candles[i + j][field];
      if (field === "low" ? left <= value || right <= value : left >= value || right >= value) {
        pivot = false;
        break;
      }
    }
    if (pivot) levels.push(value);
  }
  return levels;
}

export function swingLevels(
  candles: DisplayCandle[],
  price: number,
): { support: number[]; resistance: number[] } {
  if (!Number.isFinite(price) || candles.length < MIN_BARS) {
    return { support: [], resistance: [] };
  }
  const support = swings(candles, "low")
    .filter((level) => level < price)
    .sort((a, b) => b - a)
    .slice(0, 2);
  const resistance = swings(candles, "high")
    .filter((level) => level > price)
    .sort((a, b) => a - b)
    .slice(0, 2);
  return { support, resistance };
}

function trueRanges(candles: DisplayCandle[]): number[] {
  const ranges: number[] = [];
  for (let i = 1; i < candles.length; i += 1) {
    const current = candles[i];
    const previousClose = candles[i - 1].close;
    ranges.push(
      Math.max(
        current.high - current.low,
        Math.abs(current.high - previousClose),
        Math.abs(current.low - previousClose),
      ),
    );
  }
  return ranges;
}

function median(values: number[]): number {
  if (values.length === 0) return NaN;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

export function classifyRegime(candles: DisplayCandle[]): MarketRegime | null {
  const window = candles.slice(-48);
  if (window.length < MIN_BARS) return null;
  const ranges = trueRanges(window);
  if (ranges.length < 14) return null;
  const recent = ranges.slice(-14);
  const recentMean = recent.reduce((sum, value) => sum + value, 0) / recent.length;
  const baseline = median(ranges);
  if (!Number.isFinite(recentMean) || !Number.isFinite(baseline) || baseline <= 0) {
    return null;
  }
  if (recentMean >= baseline * 1.75) return "High Volatility";
  if (recentMean <= baseline * 0.55) return "Low Volatility";
  const closes = window.slice(-20).map((candle) => candle.close);
  const net = Math.abs(closes[closes.length - 1] - closes[0]);
  let path = 0;
  for (let i = 1; i < closes.length; i += 1) path += Math.abs(closes[i] - closes[i - 1]);
  const efficiency = path > 0 ? net / path : 0;
  if (efficiency >= 0.5) return "Trending";
  return "Ranging";
}

export function classifyMomentum(candles: DisplayCandle[]): MarketMomentum | null {
  if (candles.length < MIN_BARS) return null;
  const ranges = trueRanges(candles.slice(-15));
  if (ranges.length < 10) return null;
  const recentMean = ranges.slice(-10).reduce((sum, value) => sum + value, 0) / 10;
  const closes = candles.slice(-11).map((candle) => candle.close);
  if (closes.length < 11 || !Number.isFinite(recentMean) || recentMean <= 0) return null;
  const move = Math.abs(closes[closes.length - 1] - closes[0]);
  if (move >= recentMean * 1.5) return "Strong";
  if (move >= recentMean * 0.6) return "Moderate";
  return "Weak";
}

export function classifyDirection(
  candles: DisplayCandle[],
  signal: "BUY" | "SELL" | "WAIT" | null,
): MarketDirection | null {
  if (signal === "BUY") return "Bullish";
  if (signal === "SELL") return "Bearish";
  if (candles.length < 20) return null;
  const closes = candles.slice(-20).map((candle) => candle.close);
  const average = closes.reduce((sum, value) => sum + value, 0) / closes.length;
  const last = closes[closes.length - 1];
  const earlier = closes[closes.length - 11];
  if (last > average && last > earlier) return "Bullish";
  if (last < average && last < earlier) return "Bearish";
  return "Neutral";
}

/**
 * Gold (XAUUSD) trading session by UTC time. Single source for the top bar,
 * the Overview panel and QuantForg AI (backend uses the same windows).
 */
export function tradingSessionLabel(at: Date): string {
  const day = at.getUTCDay(); // 0 Sun … 6 Sat
  const h = at.getUTCHours();
  if (day === 6 || (day === 0 && h < 22) || (day === 5 && h >= 21)) return "Market closed";
  if (h === 21) return "Daily break";
  if (h >= 22 || h < 7) return "Asian";
  if (h < 12) return "London";
  if (h < 16) return "London / New York";
  return "New York";
}

export type FeedFreshness = {
  label: "Connecting" | "Fresh" | "Delayed" | "Stale" | "Market closed" | "Disconnected";
  tone: "fresh" | "warn" | "stale" | "down";
};

export function feedFreshness(input: {
  loading: boolean;
  error: boolean;
  hasPrice: boolean;
  status: string;
  updatedAtMs: number | null;
  nowMs: number;
}): FeedFreshness {
  if (input.loading && !input.hasPrice) return { label: "Connecting", tone: "warn" };
  const status = input.status.toLowerCase();
  if (status === "closed") return { label: "Market closed", tone: "warn" };
  if ((input.error || status === "unavailable") && !input.hasPrice) {
    return { label: "Disconnected", tone: "down" };
  }
  if (!input.hasPrice) return { label: "Disconnected", tone: "down" };
  if (status === "delayed") return { label: "Delayed", tone: "warn" };
  const age =
    input.updatedAtMs == null ? Number.POSITIVE_INFINITY : input.nowMs - input.updatedAtMs;
  if (age > 45_000) return { label: "Stale", tone: "stale" };
  if (status === "live" || status === "") return { label: "Fresh", tone: "fresh" };
  return { label: "Delayed", tone: "warn" };
}
