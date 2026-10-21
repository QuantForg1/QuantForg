/**
 * Order ticket risk vs owner limits.
 * Run: node --experimental-strip-types src/lib/execution/ticket-risk.test.ts
 */
import assert from "node:assert/strict";
import { maxSlRiskUsd, ticketRisk } from "./ticket-risk.ts";

// Owner screenshot 2026-10-21: BUY 0.01 XAUUSD, ask 4133.05, SL 4110, TP 4180.
const shot = ticketRisk({
  side: "buy",
  entry: 4133.05,
  stopLoss: 4110,
  takeProfit: 4180,
  lots: 0.01,
  contractSize: 100,
  equity: 50.84,
  spread: 0.344,
});
assert.equal(shot.riskUsd, 23.05);
assert.ok(shot.riskPctOfEquity != null && Math.abs(shot.riskPctOfEquity - 45.34) < 0.01);
assert.ok(shot.violations.some((v) => v.includes("owner cap $2.00")), shot.violations.join("; "));

// Inside the band: SL 1.80 away ($1.80), TP 3.30 away -> RR after spread 1.53.
const ok = ticketRisk({
  side: "sell",
  entry: 4133.0,
  stopLoss: 4134.8,
  takeProfit: 4129.7,
  lots: 0.01,
  contractSize: 100,
  equity: 50.84,
  spread: 0.36,
});
assert.equal(ok.riskUsd, 1.8);
assert.deepEqual(ok.violations, []);

// RR after spread too low.
const lowRr = ticketRisk({
  side: "buy",
  entry: 100,
  stopLoss: 98.2,
  takeProfit: 102,
  lots: 0.01,
  contractSize: 100,
  equity: 50.84,
  spread: 0.4,
});
assert.ok(lowRr.violations.some((v) => v.startsWith("Reward:risk after spread")));

// Below the $1.50 floor, over the lot cap, wrong side, missing stops.
assert.ok(
  ticketRisk({ side: "buy", entry: 100, stopLoss: 99, takeProfit: 105, lots: 0.01, contractSize: 100, equity: 50, spread: 0.1 })
    .violations.some((v) => v.includes("must be above $1.50")),
);
assert.ok(
  ticketRisk({ side: "buy", entry: 100, stopLoss: 98.2, takeProfit: 104, lots: 0.02, contractSize: 100, equity: 50, spread: 0.1 })
    .violations.some((v) => v.includes("exceeds owner max")),
);
assert.ok(
  ticketRisk({ side: "sell", entry: 100, stopLoss: 98, takeProfit: 104, lots: 0.01, contractSize: 100, equity: 50, spread: 0.1 })
    .violations.some((v) => v.includes("wrong side")),
);
assert.equal(
  ticketRisk({ side: "buy", entry: 100, stopLoss: NaN, takeProfit: 104, lots: 0.01, contractSize: 100, equity: 50, spread: 0.1 })
    .riskUsd,
  null,
);

assert.equal(maxSlRiskUsd(50.84), 2);
assert.equal(maxSlRiskUsd(80), 2);

console.log("ticket-risk tests passed");
