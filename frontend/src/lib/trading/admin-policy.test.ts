/**
 * Owner policy saves must not turn M1 off just because the document defers
 * to the deployment flag.
 * Run: node --experimental-strip-types src/lib/trading/admin-policy.test.ts
 */
import assert from "node:assert/strict";
import {
  buildExperimentalChanges,
  buildPolicyChanges,
  m1ChoiceFromDocument,
  policyStateLines,
  policyStatusText,
  validateActiveDraft,
  validateExperimentalDraft,
} from "./admin-policy.ts";

assert.equal(m1ChoiceFromDocument(null), "defer");
assert.equal(m1ChoiceFromDocument(undefined), "defer");
assert.equal(m1ChoiceFromDocument(true), "on");
assert.equal(m1ChoiceFromDocument(false), "off");

const changes = buildPolicyChanges({
  draft: {
    max_planned_risk_pct: "9.0",
    daily_loss_pct: "19.0",
    weekly_loss_pct: "0",
    max_lot: "0.01",
    min_lot: "",
  },
  m1: "defer",
  m1Live: "defer",
});

assert.equal(changes.m1_micro_enabled, null);
assert.equal(changes.m1_live_submit, null);
assert.equal(changes.max_concurrent_positions, 1);
assert.equal(changes.evaluate_full_utc_day, true);
assert.equal(changes.gold_only, true);
assert.equal("min_lot" in changes, false);
assert.equal(changes.weekly_loss_pct, "0");

assert.match(
  policyStatusText({ version: 0, source: "approved_baseline" }),
  /approved baseline/,
);
assert.match(
  policyStatusText({
    version: 2,
    applied_version: 2,
    worker_confirmed: true,
    source: "persisted",
  }),
  /Worker confirmed saved version 2/,
);
assert.match(
  policyStatusText({
    version: 3,
    applied_version: 2,
    worker_confirmed: false,
    source: "persisted",
  }),
  /not shown as loaded until the worker confirms version 3/,
);
assert.match(
  policyStatusText({
    version: 3,
    applied_version: 3,
    worker_confirmed: false,
    source: "persisted",
  }),
  /not shown as loaded/,
);

const active = validateActiveDraft({
  max_planned_risk_pct: "14",
  max_aggregate_open_risk_pct: "14",
  min_trade_quality: "70",
  min_reward_risk: "1.50",
});
assert.deepEqual(active, []);
const rejectedReward = validateActiveDraft({ min_reward_risk: "0.20" });
assert.equal(rejectedReward.length, 1);
assert.match(rejectedReward[0], /experimental/);
const rejectedQuality = validateActiveDraft({ min_trade_quality: "69" });
assert.match(rejectedQuality.join(" "), /70 to 100, not 75/);
const rejectedRisk = validateActiveDraft({ max_planned_risk_pct: "14.01" });
assert.match(rejectedRisk.join(" "), /14%/);

const experimentDraft = {
  max_planned_risk_pct: "14",
  max_aggregate_open_risk_pct: "14",
  daily_loss_pct: "19",
  max_lot: "0.01",
  max_spread: "0.45",
  min_reward_risk: "0.20",
  min_trade_quality: "70",
  stop_atr_multiplier: "1.00",
  max_concurrent_positions: "1",
};
assert.deepEqual(validateExperimentalDraft(experimentDraft), []);
assert.equal(
  validateExperimentalDraft({ ...experimentDraft, min_reward_risk: "1.50" }).length > 0,
  true,
);
const experimentalChanges = buildExperimentalChanges(experimentDraft);
assert.equal(experimentalChanges.promote_experimental, undefined);
const nested = experimentalChanges.experimental as Record<string, unknown>;
assert.equal(nested.min_reward_risk, "0.20");
assert.equal(nested.min_trade_quality, 70);
assert.equal("min_reward_risk" in buildPolicyChanges({
  draft: { ...experimentDraft, min_reward_risk: "1.50" },
  m1: "defer",
  m1Live: "defer",
}), true);

const states = policyStateLines({
  version: 4,
  applied_version: 2,
  worker_confirmed: false,
  experimental_promoted: false,
  experimental: { min_reward_risk: "0.20" },
  document: { min_reward_risk: "1.50", max_planned_risk_pct: "14" },
});
assert.match(states.experimental, /Saved experimental settings/);
assert.match(states.experimental, /not the live floor/);
assert.match(states.savedProduction, /not confirmed by the worker/);
assert.match(states.workerLoaded, /has not confirmed version 4/);
assert.doesNotMatch(states.workerLoaded, /0\.20/);
const loaded = policyStateLines({
  version: 4,
  applied_version: 4,
  worker_confirmed: true,
  document: { min_reward_risk: "1.50", max_planned_risk_pct: "14" },
});
assert.match(loaded.workerLoaded, /Worker loaded version 4/);
assert.match(loaded.savedProduction, /worker confirmed/i);

console.log("admin-policy.test.ts ok");
