/**
 * Order ticket SL/TP requirement.
 * Run: node --experimental-strip-types src/lib/execution/protective-stops.test.ts
 */
import assert from "node:assert/strict";
import { protectiveStopsError } from "./protective-stops.ts";

assert.equal(protectiveStopsError("4100.5", "4103.5"), null);
assert.equal(protectiveStopsError(" 4100 ", "4103"), null);

assert.equal(protectiveStopsError("", ""), "Stop loss and take profit are required");
assert.equal(protectiveStopsError(undefined, null), "Stop loss and take profit are required");
assert.equal(protectiveStopsError("", "4103.5"), "Stop loss is required");
assert.equal(protectiveStopsError("4100", ""), "Take profit is required");

for (const bad of ["0", "-1", "abc", "NaN", "Infinity", "   "]) {
  assert.equal(protectiveStopsError(bad, "4103"), "Stop loss is required", bad);
  assert.equal(protectiveStopsError("4100", bad), "Take profit is required", bad);
}

console.log("protective-stops tests passed");
