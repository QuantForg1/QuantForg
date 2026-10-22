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
};

// $50 equity -> cap $4.50. SL 4.20 + spread 0.30 = $4.50 accepted.
const atCap = ticketRisk({ ...base, stopLoss: 4128.8, takeProfit: 4140.0, spread: 0.3 });
assert.equal(atCap.riskUsd, 4.5);
assert.equal(atCap.maxSlRiskUsd, 4.5);
assert.deepEqual(atCap.violations, []);

// SL 4.21 + spread 0.30 = $4.51 rejected.
const over = ticketRisk({ ...base, stopLoss: 4128.79, takeProfit: 4140.0, spread: 0.3 });
assert.equal(over.riskUsd, 4.51);
assert.ok(over.violations.some((v) => v.includes("owner cap $4.50")), over.violations.join("; "));

// Owner screenshot: SL 23.05 away -> about $23.39 incl. spread, far above the cap.
const shot = ticketRisk({ ...base, entry: 4133.05, stopLoss: 4110, takeProfit: 4180, spread: 0.344 });
assert.ok(shot.riskUsd != null && Math.abs(shot.riskUsd - 23.39) < 0.02);
assert.ok(shot.violations.some((v) => v.includes("owner cap")));

// Dynamic cap at other equity values.
assert.equal(maxSlRiskUsd(50), 4.5);
assert.equal(maxSlRiskUsd(80), 7.2);
assert.equal(maxSlRiskUsd(33.33), 2.99);
assert.equal(maxSlRiskUsd(0), 0);

// Spread above $0.45, outside session, low RR, volume above 0.01, missing SL.
assert.ok(
  ticketRisk({ ...base, stopLoss: 4130, takeProfit: 4140, spread: 0.5 }).violations.some((v) =>
    v.startsWith("Spread"),
  ),
);
assert.ok(
  ticketRisk({ ...base, stopLoss: 4130, takeProfit: 4140, spread: 0.3, now: NIGHT }).violations.some(
    (v) => v.startsWith("Entries only"),
  ),
);
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

console.log("ticket-risk tests passed");
