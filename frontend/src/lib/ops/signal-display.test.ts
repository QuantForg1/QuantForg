/**
 * Signal Center operator labels — never fabricates BUY/SELL.
 * Run: node --experimental-strip-types src/lib/ops/signal-display.test.ts
 */
import assert from "node:assert/strict";
import {
  formatFirstBlocker,
  formatSignalHeadline,
  parseSignalPipeline,
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

assert.equal(
  formatFirstBlocker("WAIT_NO_DIRECTIONAL_EDGE"),
  "First blocker: WAIT_NO_DIRECTIONAL_EDGE",
);
assert.equal(formatFirstBlocker(null), "");

const pipeline = parseSignalPipeline({
  market: "OPEN",
  data: "LIVE",
  buy_score: 64,
  sell_score: 0,
  decision: "WAIT",
  first_blocker: "WAIT_NO_SNIPER_TRIGGER",
  sniper: "WAIT",
  risk: "NOT_REACHED",
  safety: "NOT_REACHED",
  optimizer: "NOT_REACHED",
  oms: "NOT_REACHED",
  opportunity_score: 44,
  opportunity_threshold: 70,
  execution_lifecycle: null,
});
assert.ok(pipeline);
assert.equal(pipeline.buy_score, 64);
assert.equal(pipeline.sell_score, 0);
assert.equal(pipeline.first_blocker, "WAIT_NO_SNIPER_TRIGGER");
assert.equal(pipeline.risk, "NOT_REACHED");
assert.equal(pipeline.safety, "NOT_REACHED");
assert.equal(pipeline.optimizer, "NOT_REACHED");
assert.equal(pipeline.oms, "NOT_REACHED");
assert.equal(pipeline.opportunity_threshold, 70);
assert.equal(pipeline.execution_lifecycle, null);

console.log("signal-display.test.ts: ok");
