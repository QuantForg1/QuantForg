/**
 * Order ticket risk vs owner limits (9% planned risk, spread included).
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

// $50 equity -> cap $4.50. SL 4.20 + spread 0.30 = $4.50 accepted.
// TP clears owner min reward:risk 1.50 (reward 7.00 on risk 4.50 = 1.56).
const atCap = ticketRisk({
  ...base,
  stopLoss: 4128.8,
  takeProfit: 4140.0,
  spread: 0.3,
});
assert.equal(atCap.riskUsd, 4.5);
assert.equal(atCap.maxSlRiskUsd, 4.5);
assert.deepEqual(atCap.violations, []);

// SL 4.21 + spread 0.30 = $4.51 rejected.
const over = ticketRisk({
  ...base,
  stopLoss: 4128.79,
  takeProfit: 4140.0,
  spread: 0.3,
});
assert.equal(over.riskUsd, 4.51);
assert.ok(over.violations.some((v) => v.includes("owner cap $4.50")), over.violations.join("; "));

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
assert.equal(maxSlRiskUsd(50), 4.5);
assert.equal(maxSlRiskUsd(80), 7.2);
assert.equal(maxSlRiskUsd(33.33), 2.99);
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
// Entries Monday-Friday, 24 hours (24/5).
assert.ok(
  ticketRisk({ ...base, stopLoss: 4130, takeProfit: 4140, spread: 0.46 }).violations.some((v) =>
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
assert.deepEqual(night.violations, []); // 24/5: night entries allowed
const weekend = ticketRisk({
  ...base,
  stopLoss: 4130,
  takeProfit: 4140,
  spread: 0.3,
  now: new Date("2026-10-24T10:00:00Z"),
});
assert.deepEqual(weekend.violations, ["Entries only Mon–Fri, 24 hours (24/5) UTC"]);
const open = ticketRisk({
  ...base,
  stopLoss: 4130,
  takeProfit: 4140,
  spread: 0.3,
  now: new Date("2026-10-22T07:00:00Z"),
});
assert.deepEqual(open.violations, []);
const close = ticketRisk({
  ...base,
  stopLoss: 4130,
  takeProfit: 4140,
  spread: 0.3,
  now: new Date("2026-10-22T17:00:00Z"),
});
assert.deepEqual(close.violations, []); // 17:00 UTC is inside 24/5
// RR ≈ 0.12 < 1.50 floor (risk 3.3, reward 0.4) — buy TP above entry.
assert.ok(
  ticketRisk({ ...base, stopLoss: 4130, takeProfit: 4133.4, spread: 0.3 }).violations.some((v) =>
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

// Equity 29.86 → cap $2.68. Stop 2.380 + spread 0.310 = $2.69.
const reported = ticketRisk({
  ...base,
  equity: 29.86,
  entry: 4000,
  stopLoss: 3997.62,
  takeProfit: 4010,
  spread: 0.31,
});
assert.equal(reported.maxSlRiskUsd, 2.68);
assert.equal(reported.riskUsd, 2.69);
assert.ok(reported.violations.some((v) => v.includes("$2.69 > owner cap $2.68")));
assert.equal(reported.fittedStopDistance, 2.37);
assert.ok(reported.correction?.includes("2.37"));

// 2.681 must ceiling to $2.69 and fail. It must not half-even down to $2.68.
const raw = ticketRisk({
  ...base,
  equity: 29.86,
  entry: 4000,
  stopLoss: 3997.319,
  takeProfit: 4010,
  spread: 0,
});
assert.equal(raw.riskUsd, 2.69);
assert.ok(raw.violations.some((v) => v.includes("owner cap $2.68")));

// Exact cap still passes. One extra cent fails.
assert.deepEqual(
  ticketRisk({
    ...base,
    equity: 29.86,
    entry: 4000,
    stopLoss: 3997.32,
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
    stopLoss: 3997.31,
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
