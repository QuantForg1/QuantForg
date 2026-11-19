import assert from "node:assert/strict";
import {
  formatCountdown,
  formatPrice,
  formatUtcTime,
  impactTone,
  minutesUntil,
  regimeLabels,
  relativeTime,
  strategyFit,
} from "./desk-format.ts";

assert.equal(formatPrice(3675.333), "3,675.33");
assert.equal(formatPrice(Number.NaN), "—");
assert.equal(formatUtcTime("2026-11-19T19:22:43+00:00"), "19:22 UTC");
assert.equal(formatUtcTime("bad"), "");

const now = Date.parse("2026-11-19T19:00:00Z");
assert.equal(minutesUntil("2026-11-19T19:30:00Z", now), 30);
assert.equal(relativeTime("2026-11-19T18:45:00Z", now), "15 min ago");
assert.equal(relativeTime("2026-11-19T16:00:00Z", now), "3 h ago");

assert.equal(impactTone("High"), "danger");
assert.equal(impactTone("medium"), "warning");
assert.equal(impactTone("low"), "neutral");

assert.deepEqual(regimeLabels({ direction: "bearish", aligned: 3, of: 3 }, { state: "high" }), [
  "Trending",
  "High Volatility",
]);
assert.deepEqual(regimeLabels({ direction: "bearish", aligned: 2, of: 3 }, { state: "normal" }), ["Range / mixed"]);
assert.equal(strategyFit(["Trending", "High Volatility"], ["Trending", "High Volatility"]), 2);
assert.equal(strategyFit(["Range / mixed"], ["Trending"]), 0);

assert.equal(formatCountdown(1199.6), "20 h");
assert.equal(formatCountdown(95), "1 h 35 min");
assert.equal(formatCountdown(12), "12 min");
assert.equal(formatCountdown(-5), "0 min");
assert.equal(formatCountdown(26 * 60 + 10), "1 d 2 h");

console.log("desk-format: ok");
