/**
 * Order ticket risk vs owner limits (14% planned risk, spread included).
 * Run: node --experimental-strip-types src/lib/execution/ticket-risk.test.ts
 */
import assert from "node:assert/strict";
import { maxSlRiskUsd, ticketRisk } from "./ticket-risk.ts";

const LONDON = new Date("2026-10-22T10:00:00Z");
const NIGHT = new Date("2026-10-22T22:00:00Z");
const base = {
  side: "buy" as const,
  entry: 4133.0,
  lots: 0.01,
  contractSize: 100,
  equity: 50,
  now: LONDON,
  commission: 0,
};

// $50 equity -> cap $7.00. SL 6.70 + spread 0.30 = $7.00 accepted.
const atCap = ticketRisk({
  ...base,
  stopLoss: 4126.3,
  takeProfit: 4143.5,
  spread: 0.3,
});
assert.equal(atCap.riskUsd, 7);
assert.equal(atCap.maxSlRiskUsd, 7);
assert.deepEqual(atCap.violations, []);

// SL 6.71 + spread 0.30 = $7.01 rejected.
const over = ticketRisk({
  ...base,
  stopLoss: 4126.29,
  takeProfit: 4144.0,
  spread: 0.3,
});
assert.equal(over.riskUsd, 7.01);
assert.ok(over.violations.some((v) => v.includes("owner cap $7.00")), over.violations.join("; "));

// Owner screenshot: SL 23.05 away -> about $23.39 incl. spread, far above the cap.
const shot = ticketRisk({
  ...base,
  entry: 4133.05,
  stopLoss: 4110,
  takeProfit: 4180,
  spread: 0.344,
});
assert.ok(shot.riskUsd != null && Math.abs(shot.riskUsd - 23.39) < 0.02);
assert.ok(shot.violations.some((v) => v.includes("owner cap")));

// Dynamic cap at other equity values.
assert.equal(maxSlRiskUsd(50), 7);
assert.equal(maxSlRiskUsd(80), 11.2);
assert.equal(maxSlRiskUsd(33.33), 4.66);
assert.equal(maxSlRiskUsd(0), 0);

// Omitted commission is unknown. A present zero is a known zero.
const unknownFee = ticketRisk({
  side: "buy",
  entry: 4133,
  stopLoss: 4126.3,
  takeProfit: 4143.5,
  lots: 0.01,
  contractSize: 100,
  equity: 50,
  spread: 0.3,
  now: LONDON,
});
assert.equal(unknownFee.riskUsd, null);
assert.ok(unknownFee.violations.some((v) => v.startsWith("Commission unknown")));
const negativeFee = ticketRisk({ ...base, stopLoss: 4130, takeProfit: 4140, spread: 0.3, commission: -1 });
assert.equal(negativeFee.riskUsd, null);
assert.ok(negativeFee.violations.some((v) => v.includes("cannot be negative")));

// Spread above $0.45, low RR, volume above 0.01, missing SL.
// 22:00 UTC is inside the full-day window: the old 07:00-17:00 gate must not fire.
assert.ok(
  ticketRisk({ ...base, stopLoss: 4130, takeProfit: 4140, spread: 0.5 }).violations.some((v) =>
    v.startsWith("Spread"),
  ),
);
const night = ticketRisk({
  ...base,
  stopLoss: 4130,
  takeProfit: 4140,
  spread: 0.3,
  now: NIGHT,
});
assert.equal(
  night.violations.some((v) => v.startsWith("Entries only")),
  false,
);
assert.deepEqual(night.violations, []);
const weekend = ticketRisk({
  ...base,
  stopLoss: 4130,
  takeProfit: 4140,
  spread: 0.3,
  now: new Date("2026-10-24T10:00:00Z"),
});
assert.deepEqual(weekend.violations, []);
assert.ok(
  ticketRisk({ ...base, stopLoss: 4130, takeProfit: 4134, spread: 0.3 }).violations.some((v) =>
    v.startsWith("Reward:risk"),
  ),
);
assert.ok(
  ticketRisk({ ...base, lots: 0.02, stopLoss: 4131, takeProfit: 4140, spread: 0.3 }).violations.some(
    (v) => v.includes("exceeds owner max"),
  ),
);
assert.equal(
  ticketRisk({ ...base, stopLoss: NaN, takeProfit: 4140, spread: 0.3 }).riskUsd,
  null,
);

// No minimum planned-risk floor: a small, valid stop is fine.
assert.deepEqual(
  ticketRisk({ ...base, stopLoss: 4132.0, takeProfit: 4135.0, spread: 0.3 }).violations,
  [],
);

// Equity 29.86 → cap $4.18. Stop 4.000 + spread 0.310 = $4.31.
const reported = ticketRisk({
  ...base,
  equity: 29.86,
  entry: 4000,
  stopLoss: 3996,
  takeProfit: 4010,
  spread: 0.31,
});
assert.equal(reported.maxSlRiskUsd, 4.18);
assert.equal(reported.riskUsd, 4.31);
assert.ok(reported.violations.some((v) => v.includes("$4.31 > owner cap $4.18")));
assert.equal(reported.fittedStopDistance, 3.87);
assert.ok(reported.correction?.includes("3.87"));

// 4.181 must ceiling to $4.19 and fail. It must not half-even down to $4.18.
const raw = ticketRisk({
  ...base,
  equity: 29.86,
  entry: 4000,
  stopLoss: 3995.819,
  takeProfit: 4010,
  spread: 0,
});
assert.equal(raw.riskUsd, 4.19);
assert.ok(raw.violations.some((v) => v.includes("owner cap $4.18")));

// Exact cap still passes. One extra cent fails.
assert.deepEqual(
  ticketRisk({
    ...base,
    equity: 29.86,
    entry: 4000,
    stopLoss: 3995.82,
    takeProfit: 4010,
    spread: 0,
  }).violations,
  [],
);
assert.ok(
  ticketRisk({
    ...base,
    equity: 29.86,
    entry: 4000,
    stopLoss: 3995.81,
    takeProfit: 4010,
    spread: 0,
  }).violations.some((v) => v.startsWith("Planned risk")),
);

// Supplied slippage is included. Omitting it does not invent a charge.
assert.equal(
  ticketRisk({ ...base, stopLoss: 4126.3, takeProfit: 4143.5, spread: 0.3, slippage: 0.01 }).riskUsd,
  7.01,
);

console.log("ticket-risk tests passed");
