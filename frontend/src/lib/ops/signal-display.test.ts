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
  opportunity_gate: "WAIT",
  setup_state: "WAIT",
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
assert.equal(pipeline.broker, "NOT_REACHED");
assert.equal(pipeline.mt5, "NOT_REACHED");
assert.equal(pipeline.candidate, "NONE");
assert.equal(pipeline.final_decision, "WAIT");
assert.equal(pipeline.opportunity_threshold, 70);
assert.equal(pipeline.opportunity_gate, "WAIT");
assert.equal(pipeline.setup_state, "WAIT");
assert.equal(pipeline.execution_lifecycle, null);
assert.deepEqual(pipeline.buy_components, {});
assert.deepEqual(pipeline.sell_components, {});

const liveChase = parseSignalPipeline({
  market: "OPEN",
  data: "LIVE",
  buy_score: 6,
  sell_score: 48,
  decision: "WAIT",
  first_blocker: "WAIT_CHASE",
  sniper: "WAIT",
  risk: "NOT_REACHED",
  safety: "NOT_REACHED",
  optimizer: "NOT_REACHED",
  oms: "NOT_REACHED",
  opportunity_score: 73,
  opportunity_threshold: 70,
  opportunity_gate: "PASS",
  setup_state: "INVALIDATED",
  execution_lifecycle: null,
});
assert.ok(liveChase);
assert.equal(liveChase.opportunity_gate, "PASS");
assert.equal(liveChase.sniper, "WAIT");
assert.equal(liveChase.first_blocker, "WAIT_CHASE");
assert.equal(liveChase.risk, "NOT_REACHED");
assert.equal(liveChase.sniper_tier, null);

const readyTier = parseSignalPipeline({
  market: "OPEN",
  data: "LIVE",
  buy_score: 72,
  sell_score: 31,
  decision: "BUY",
  first_blocker: null,
  sniper: "READY",
  risk: "NOT_REACHED",
  safety: "NOT_REACHED",
  optimizer: "NOT_REACHED",
  oms: "NOT_REACHED",
  opportunity_score: 81,
  opportunity_threshold: 70,
  opportunity_gate: "PASS",
  setup_state: "SETUP_READY",
  sniper_tier: "A",
  market_regime: "TREND_UP",
  entry_state: "RETEST",
  execution_lifecycle: null,
});
assert.ok(readyTier);
assert.equal(readyTier.sniper_tier, "A");
assert.equal(readyTier.market_regime, "TREND_UP");
assert.equal(readyTier.entry_state, "RETEST");
assert.equal(readyTier.setup_state, "SETUP_READY");

const capacityFull = parseSignalPipeline({
  market: "OPEN",
  data: "LIVE",
  buy_score: 6,
  sell_score: 48,
  decision: "SELL",
  first_blocker: "MAX_POSITIONS_REACHED",
  sniper: "READY",
  risk: "BLOCK",
  safety: "NOT_REACHED",
  optimizer: "NOT_REACHED",
  oms: "NOT_REACHED",
  broker: "NOT_REACHED",
  mt5: "NOT_REACHED",
  opportunity_score: 75,
  opportunity_threshold: 70,
  opportunity_gate: "PASS",
  setup_state: "TAKE",
  final_decision: "TAKE",
  execution_lifecycle: "EXECUTION_BLOCKED",
});
assert.ok(capacityFull);
assert.equal(capacityFull.decision, "SELL");
assert.equal(capacityFull.final_decision, "TAKE");
assert.equal(capacityFull.sniper, "READY");
assert.equal(capacityFull.risk, "BLOCK");
assert.equal(capacityFull.safety, "NOT_REACHED");
assert.equal(capacityFull.optimizer, "NOT_REACHED");
assert.equal(capacityFull.oms, "NOT_REACHED");
assert.equal(capacityFull.broker, "NOT_REACHED");
assert.equal(capacityFull.mt5, "NOT_REACHED");
assert.equal(capacityFull.first_blocker, "MAX_POSITIONS_REACHED");

const dailyLoss = parseSignalPipeline({
  market: "OPEN",
  data: "LIVE",
  buy_score: 6,
  sell_score: 48,
  decision: "SELL",
  first_blocker: "DAILY_LOSS_BLOCK",
  sniper: "READY",
  risk: "BLOCK",
  safety: "NOT_REACHED",
  optimizer: "NOT_REACHED",
  oms: "NOT_REACHED",
  broker: "NOT_REACHED",
  mt5: "NOT_REACHED",
  opportunity_score: 71,
  opportunity_threshold: 70,
  opportunity_gate: "PASS",
  setup_state: "TAKE",
  final_decision: "TAKE",
  execution_lifecycle: "EXECUTION_BLOCKED",
});
assert.ok(dailyLoss);
assert.equal(dailyLoss.final_decision, "TAKE");
assert.equal(dailyLoss.sniper, "READY");
assert.equal(dailyLoss.risk, "BLOCK");
assert.equal(dailyLoss.safety, "NOT_REACHED");
assert.equal(dailyLoss.oms, "NOT_REACHED");
assert.equal(dailyLoss.broker, "NOT_REACHED");
assert.equal(dailyLoss.mt5, "NOT_REACHED");
assert.equal(dailyLoss.first_blocker, "DAILY_LOSS_BLOCK");
assert.equal(
  formatFirstBlocker("DAILY_LOSS_BLOCK"),
  "First blocker: DAILY_LOSS_BLOCK",
);

console.log("signal-display.test.ts: ok");
