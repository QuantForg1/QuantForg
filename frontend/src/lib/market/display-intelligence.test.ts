import assert from "node:assert/strict";
import {
  classifyDirection,
  classifyMomentum,
  classifyRegime,
  confirmedCandles,
  feedFreshness,
  swingLevels,
  tradingSessionLabel,
  type DisplayCandle,
} from "./display-intelligence.ts";

function bars(
  count: number,
  at: (index: number) => { high: number; low: number; close: number },
): DisplayCandle[] {
  return Array.from({ length: count }, (_, index) => {
    const price = at(index);
    return {
      time: 1_700_000_000 + index * 900,
      open: price.close,
      high: price.high,
      low: price.low,
      close: price.close,
    };
  });
}

const now = 1_700_000_000 + 40 * 900;
const formingNow = 1_700_000_000 + 29 * 900 + 30;
const closed = confirmedCandles(
  bars(30, () => ({ high: 110, low: 90, close: 100 })),
  "M15",
  formingNow,
);
assert.equal(closed.length, 29);

const pivots = bars(30, (index) => {
  if (index === 10) return { high: 105, low: 90, close: 100 };
  if (index === 20) return { high: 130, low: 100, close: 110 };
  return { high: 112, low: 100, close: 106 };
});
const levels = swingLevels(confirmedCandles(pivots, "M15", now), 110);
assert.ok(levels.support.includes(90));
assert.ok(levels.resistance.includes(130));
assert.deepEqual(swingLevels(closed.slice(0, 10), 100), {
  support: [],
  resistance: [],
});

const trend = confirmedCandles(
  bars(30, (index) => ({
    high: 100 + index + 0.2,
    low: 100 + index - 0.2,
    close: 100 + index,
  })),
  "M15",
  now,
);
assert.equal(classifyRegime(trend), "Trending");
assert.equal(classifyMomentum(trend), "Strong");
assert.equal(classifyDirection(trend, "WAIT"), "Bullish");
assert.equal(classifyDirection(trend, "SELL"), "Bearish");

const quiet = confirmedCandles(
  bars(30, () => ({ high: 100.05, low: 99.95, close: 100 })),
  "M15",
  now,
);
assert.equal(classifyDirection(quiet, null), "Neutral");
assert.equal(classifyRegime(quiet.slice(0, 10)), null);

const burst = bars(40, (index) =>
  index < 24
    ? { high: 100.1, low: 99.9, close: 100 }
    : { high: 120, low: 80, close: 100 },
);
assert.equal(classifyRegime(confirmedCandles(burst, "M15", now)), "High Volatility");

assert.equal(tradingSessionLabel(new Date("2026-01-15T08:30:00Z")), "London");
assert.equal(
  tradingSessionLabel(new Date("2026-01-15T13:00:00Z")),
  "London / New York",
);
assert.equal(tradingSessionLabel(new Date("2026-01-15T18:00:00Z")), "New York");
assert.equal(tradingSessionLabel(new Date("2026-01-15T22:30:00Z")), "Asian");
assert.equal(tradingSessionLabel(new Date("2026-01-15T21:30:00Z")), "Daily break");
assert.equal(tradingSessionLabel(new Date("2026-01-15T13:00:00Z")), "London / New York");
assert.equal(tradingSessionLabel(new Date("2026-01-17T12:00:00Z")), "Market closed");

assert.equal(
  feedFreshness({
    loading: false,
    error: false,
    hasPrice: true,
    status: "live",
    updatedAtMs: 10_000,
    nowMs: 20_000,
  }).label,
  "Fresh",
);
assert.equal(
  feedFreshness({
    loading: false,
    error: false,
    hasPrice: true,
    status: "live",
    updatedAtMs: 0,
    nowMs: 60_000,
  }).label,
  "Stale",
);
assert.equal(
  feedFreshness({
    loading: true,
    error: false,
    hasPrice: false,
    status: "",
    updatedAtMs: null,
    nowMs: 0,
  }).label,
  "Connecting",
);

console.log("display-intelligence: ok");
