/**
 * Lot sizing must not round a sub-minimum budget up to 0.01.
 * Run: node --experimental-strip-types src/lib/execution/position-sizing.test.ts
 */
import assert from "node:assert/strict";
import { lotsFromRiskBudget, normalizeLot } from "./position-sizing.ts";

const gold = {
  contractSize: 100,
  minLot: 0.01,
  maxLot: 0.01,
  lotStep: 0.01,
};

// $2.68 budget cannot buy 0.01 lot when the stop plus spread is 2.71.
assert.equal(
  lotsFromRiskBudget({
    ...gold,
    equity: 29.86,
    riskPct: 9,
    stopDistance: 2.4,
    spread: 0.31,
    maxRiskUsd: 2.68,
  }),
  null,
);

// Exact $4.50 at the minimum lot is legal.
assert.equal(
  lotsFromRiskBudget({
    ...gold,
    equity: 50,
    riskPct: 9,
    stopDistance: 4.2,
    spread: 0.3,
    maxRiskUsd: 4.5,
  }),
  0.01,
);

// A 1% budget on this stop is below the minimum lot. Do not upsize.
assert.equal(
  lotsFromRiskBudget({
    ...gold,
    equity: 50,
    riskPct: 1,
    stopDistance: 4.2,
    spread: 0.3,
    maxRiskUsd: 4.5,
  }),
  null,
);

// Ceiling: 2.681 must not be treated as a $2.68 pass.
assert.equal(
  lotsFromRiskBudget({
    ...gold,
    equity: 29.86,
    riskPct: 9,
    stopDistance: 2.681,
    spread: 0,
    maxRiskUsd: 2.68,
  }),
  null,
);

assert.equal(normalizeLot(0.01, 0.01, 0.01, 0.01), 0.01);
assert.equal(normalizeLot(0.019, 0.01, 0.01, 0.01), 0.01);
assert.equal(normalizeLot(0.009, 0.01, 0.01, 0.01), null);

console.log("position-sizing tests passed");
