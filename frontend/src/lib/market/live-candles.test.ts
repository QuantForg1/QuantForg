import assert from "node:assert/strict";
import { applyLivePrice, clockOffsetSeconds, type Bar } from "./live-candles.ts";

const T = 1_795_125_600; // aligned to the minute
const bars = (): Bar[] => [
  { time: T - 60, open: 10, high: 11, low: 9, close: 10.5 },
  { time: T, open: 10.5, high: 10.8, low: 10.2, close: 10.6 },
];

// same bar: updates close/high/low
let b = bars();
let r = applyLivePrice(b, 11.2, T + 30, 60, 0);
assert.ok(r && !r.isNew);
assert.equal(b[1].close, 11.2);
assert.equal(b[1].high, 11.2);

// next minute: opens a new bar at the previous close
b = bars();
r = applyLivePrice(b, 10.1, T + 65, 60, 0);
assert.ok(r && r.isNew);
assert.equal(b.length, 3);
assert.equal(b[2].time, T + 60);
assert.equal(b[2].open, 10.6);
assert.equal(b[2].low, 10.1);

// broker clock UTC+2: bars are 7200 s ahead of wall clock
b = bars();
const off = clockOffsetSeconds(T, T - 7200 + 20, 60);
assert.equal(off, 7200);
r = applyLivePrice(b, 10.7, T - 7200 + 20, 60, off);
assert.ok(r && !r.isNew);

// UTC feed lagging one bar is not treated as an offset
assert.equal(clockOffsetSeconds(T, T + 70, 60), 0);
// closed market (old last bar) -> no offset, and no invented bars
assert.equal(clockOffsetSeconds(T, T + 3 * 86400, 60), 0);
b = bars();
assert.equal(applyLivePrice(b, 10, T + 3 * 86400, 60, 0), null);
// garbage price ignored
assert.equal(applyLivePrice(bars(), Number.NaN, T + 5, 60, 0), null);

console.log("live-candles: ok");
