import assert from "node:assert/strict";
import {
  coachAnswerText,
  figureText,
  RELIABILITY_COMPONENTS,
  reliabilityLabel,
} from "./account-reports.ts";

assert.equal(figureText(undefined), "Unavailable");
assert.equal(figureText({ value: null, status: "unavailable" }), "unavailable");
assert.equal(figureText({ value: 0, status: "verified" }), "0");
assert.equal(reliabilityLabel({}, "gateway"), "Unknown");
assert.equal(
  reliabilityLabel({ components: [{ name: "gateway", state: "healthy" }] }, "gateway"),
  "healthy",
);
assert.equal(
  reliabilityLabel({ components: [{ name: "gateway", state: "fine" }] }, "gateway"),
  "Unknown",
);
assert.equal(reliabilityLabel({ components: [] }, "mt5"), "Unknown");
assert.equal(coachAnswerText({ status: "unavailable", answer: 12 }), "Unavailable");
assert.equal(coachAnswerText({ status: "grounded", answer: "stop_rejected" }), "stop_rejected");
assert.equal(RELIABILITY_COMPONENTS.length, 8);
console.log("account reports ok");
