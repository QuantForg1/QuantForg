/**
 * Sample-size labels must never display a fake 80–90% win rate.
 * Run: node --experimental-strip-types src/lib/ops/sample-confidence.test.ts
 */
import assert from "node:assert/strict";
import {
  EARLY_SIGNAL,
  HIGHER_CONFIDENCE,
  INSUFFICIENT_SAMPLE,
  MEANINGFUL_RESEARCH,
  PRELIMINARY,
  STRONGER_EVIDENCE,
  displayMetric,
  formatRate,
  sampleStatus,
} from "./sample-confidence.ts";

assert.equal(sampleStatus(0), INSUFFICIENT_SAMPLE);
assert.equal(sampleStatus(1), EARLY_SIGNAL);
assert.equal(sampleStatus(4), EARLY_SIGNAL);
assert.equal(sampleStatus(9), EARLY_SIGNAL);
assert.equal(sampleStatus(10), PRELIMINARY);
assert.equal(sampleStatus(19), PRELIMINARY);
assert.equal(sampleStatus(20), MEANINGFUL_RESEARCH);
assert.equal(sampleStatus(49), MEANINGFUL_RESEARCH);
assert.equal(sampleStatus(50), STRONGER_EVIDENCE);
assert.equal(sampleStatus(99), STRONGER_EVIDENCE);
assert.equal(sampleStatus(100), HIGHER_CONFIDENCE);
assert.equal(displayMetric("90%", INSUFFICIENT_SAMPLE), "INSUFFICIENT SAMPLE");
assert.equal(displayMetric("1.2", EARLY_SIGNAL), "1.2");
assert.equal(displayMetric("UNKNOWN", PRELIMINARY), "INSUFFICIENT SAMPLE");
assert.equal(formatRate(72.4, 87, PRELIMINARY), "72.4% n=87");
assert.equal(formatRate(90, 3), "INSUFFICIENT SAMPLE n=3");
assert.equal(formatRate(90, 7, EARLY_SIGNAL), "INSUFFICIENT SAMPLE n=7");
assert.equal(formatRate(90, 5, EARLY_SIGNAL), "INSUFFICIENT SAMPLE n=5");

console.log("sample-confidence.test.ts ok");
