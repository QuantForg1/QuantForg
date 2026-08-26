/**
 * Signal Center operator labels — never fabricates BUY/SELL.
 * Run: node --experimental-strip-types src/lib/ops/signal-display.test.ts
 */
import assert from "node:assert/strict";
import {
  formatSignalHeadline,
  signalDirectionGlyph,
} from "./signal-display.ts";

assert.equal(
  formatSignalHeadline("WAIT", "WAIT — opportunity score below threshold"),
  "WAIT — opportunity score below threshold",
);
assert.equal(
  formatSignalHeadline("WAIT", "opportunity score below threshold"),
  "WAIT — opportunity score below threshold",
);
assert.equal(formatSignalHeadline("WAIT", null), "WAIT — setup not confirmed");
assert.equal(formatSignalHeadline("BUY", null), "BUY — sniper setup confirmed");
assert.equal(
  formatSignalHeadline("SELL", "SELL — bearish liquidity sweep + BOS"),
  "SELL — bearish liquidity sweep + BOS",
);
assert.equal(signalDirectionGlyph("WAIT"), "WAIT");
assert.equal(signalDirectionGlyph("BUY"), "BUY");
assert.equal(signalDirectionGlyph("NONE"), "NONE");

console.log("signal-display.test.ts: ok");
