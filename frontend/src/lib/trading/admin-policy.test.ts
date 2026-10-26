/**
 * Owner policy saves must not turn M1 off just because the document defers
 * to the deployment flag.
 * Run: node --experimental-strip-types src/lib/trading/admin-policy.test.ts
 */
import assert from "node:assert/strict";
import {
  buildPolicyChanges,
  m1ChoiceFromDocument,
  policyStatusText,
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
  policyStatusText({ version: 2, applied_version: 2, source: "persisted" }),
  /applied/,
);
assert.match(
  policyStatusText({ version: 3, applied_version: 2, source: "persisted" }),
  /next cycle/,
);

console.log("admin-policy.test.ts ok");
