/**
 * Signal Center operator labels — never fabricates BUY/SELL.
 * Run: node --experimental-strip-types src/lib/ops/signal-display.test.ts
 */
import assert from "node:assert/strict";
import {
  classifyExecutionBlocker,
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
assert.equal(pipeline.eligibility_status, null);
assert.equal(pipeline.eligibility_reason, null);
assert.equal(pipeline.blocker_category, null);
assert.equal(pipeline.execution_stage, null);
assert.equal(pipeline.forwarded_to_oms, null);
assert.equal(pipeline.ticket, null);

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
assert.equal(liveChase.directional_edge, null);
assert.equal(liveChase.confluence_class, null);
assert.equal(liveChase.setup_family, null);
assert.equal(liveChase.h1_context, "context-only");

const staleFamily = parseSignalPipeline({
  market: "OPEN",
  data: "LIVE",
  buy_score: 16,
  sell_score: 42,
  decision: "WAIT",
  first_blocker: "WAIT_STALE_FVG",
  sniper: "WAIT",
  risk: "NOT_REACHED",
  safety: "NOT_REACHED",
  optimizer: "NOT_REACHED",
  oms: "NOT_REACHED",
  opportunity_score: 70,
  opportunity_threshold: 70,
  opportunity_gate: "PASS",
  setup_state: "STALE",
  setup_family: "stale_fvg",
  confluence_class: "INVALID",
  execution_lifecycle: null,
});
assert.ok(staleFamily);
assert.equal(staleFamily.first_blocker, "WAIT_STALE_FVG");
assert.equal(staleFamily.setup_family, "stale_fvg");
assert.equal(staleFamily.opportunity_gate, "PASS");
assert.equal(staleFamily.risk, "NOT_REACHED");
assert.equal(staleFamily.oms, "NOT_REACHED");

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

const burstBlocked = parseSignalPipeline({
  market: "OPEN",
  data: "LIVE",
  buy_score: 6,
  sell_score: 48,
  decision: "SELL",
  first_blocker: "EXECUTION_REJECT_BURST",
  sniper: "READY",
  risk: "READY",
  safety: "READY",
  optimizer: "NOT_REACHED",
  oms: "NOT_REACHED",
  broker: "NOT_REACHED",
  mt5: "NOT_REACHED",
  opportunity_score: 77,
  opportunity_threshold: 70,
  opportunity_gate: "PASS",
  setup_state: "TAKE",
  final_decision: "TAKE",
  execution_lifecycle: "EXECUTION_BLOCKED",
  blocker_category: "EXECUTION_REJECT_BURST",
  reject_burst: {
    active: true,
    count: 5,
    window: 120,
    last_event_stage: "MT5_REJECTED",
    remaining_cooldown: 240,
  },
  execution_attempted: false,
  oms_reached: false,
  broker_reached: false,
  mt5_reached: false,
  reject_source: "EXECUTION_REJECT_BURST",
  reject_burst_count: 5,
  reject_burst_window_seconds: 120,
});
assert.ok(burstBlocked);
assert.equal(burstBlocked.first_blocker, "EXECUTION_REJECT_BURST");
assert.equal(burstBlocked.risk, "READY");
assert.equal(burstBlocked.oms, "NOT_REACHED");
assert.equal(burstBlocked.broker, "NOT_REACHED");
assert.equal(burstBlocked.mt5, "NOT_REACHED");
assert.equal(burstBlocked.ticket, null);
assert.equal(burstBlocked.reject_burst?.active, true);
assert.equal(burstBlocked.execution_attempted, false);
assert.equal(burstBlocked.oms_reached, false);
assert.equal(burstBlocked.mt5_reached, false);
assert.equal(burstBlocked.reject_source, "EXECUTION_REJECT_BURST");
assert.equal(burstBlocked.reject_burst_count, 5);
assert.equal(burstBlocked.reject_burst_window_seconds, 120);
assert.equal(
  classifyExecutionBlocker("phase_a:REJECT_BURST"),
  "EXECUTION_REJECT_BURST",
);
assert.equal(classifyExecutionBlocker("RISK_REJECTED"), "RISK_REJECTED");
assert.equal(classifyExecutionBlocker("SAFETY_BLOCKED"), "SAFETY_BLOCKED");
assert.equal(classifyExecutionBlocker("OMS_REJECTED"), "OMS_REJECTED");
assert.equal(classifyExecutionBlocker("BROKER_REJECTED"), "BROKER_REJECTED");
assert.equal(classifyExecutionBlocker("MT5_REJECTED"), "MT5_REJECTED");
assert.equal(classifyExecutionBlocker("WAIT_NO_SNIPER_TRIGGER"), null);

console.log("signal-display.test.ts: ok");
