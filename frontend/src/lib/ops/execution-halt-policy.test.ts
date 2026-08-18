/**
 * Soft vs hard execution halt classification.
 * Run: node --experimental-strip-types src/lib/ops/execution-halt-policy.test.ts
 */
import assert from "node:assert/strict";
import {
  classifyHaltCondition,
  doesNotHaltNewEntry,
  haltsNewEntry,
} from "./execution-halt-policy";

const advisory = [
  "UI/telemetry stale",
  "duplicate health probe",
  "optional enrichment unavailable",
  "non-authoritative analytics unavailable",
];
for (const reason of advisory) {
  assert.equal(classifyHaltCondition(reason), "advisory");
  assert.equal(doesNotHaltNewEntry(reason), true);
  assert.equal(haltsNewEntry(reason), false);
}

const hard = [
  "MT5 disconnected",
  "Gateway unavailable",
  "stale quote",
  "invalid symbol",
  "risk limit exceeded",
  "Safety failure",
  "minimum lot causes risk violation",
  "reconciliation unknown",
];
for (const reason of hard) {
  assert.equal(classifyHaltCondition(reason), "hard_block");
  assert.equal(haltsNewEntry(reason), true);
  assert.equal(doesNotHaltNewEntry(reason), false);
}

assert.equal(classifyHaltCondition("stale quote"), "hard_block");
assert.equal(classifyHaltCondition("UI/telemetry stale"), "advisory");

console.log("execution-halt-policy.test.ts: ok");
