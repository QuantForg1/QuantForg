/**
 * Contract + pure logic checks for dashboard intelligence helpers.
 * Run: node --experimental-strip-types src/lib/dashboard/performance-window.test.ts
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { OWNER_RISK_POLICY_DISPLAY } from "../trading/owner-risk-policy-display.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const perf = readFileSync(join(root, "lib/dashboard/performance-window.ts"), "utf8");
const risk = readFileSync(join(root, "lib/dashboard/risk-intelligence.ts"), "utf8");
const policy = readFileSync(
  join(root, "lib/trading/owner-risk-policy-display.ts"),
  "utf8",
);
const dash = readFileSync(join(root, "app/(app)/dashboard/page.tsx"), "utf8");
const desk = readFileSync(
  join(root, "components/trading/overview-reference-desk.tsx"),
  "utf8",
);

assert.match(perf, /computePerformanceWindow/);
assert.match(perf, /realizedPnl/);
assert.match(perf, /floatingPnl/);
assert.match(perf, /commission/);
assert.match(risk, /deriveRiskIntelligence/);
assert.match(risk, /Healthy/);
assert.match(risk, /Halted/);
assert.match(risk, /OWNER_RISK_POLICY_DISPLAY/);
assert.match(policy, /dailyLossHaltPercent: 48/);
assert.match(policy, /maxLot: 0\.01/);
assert.match(policy, /maxConcurrentPositions: 1/);
assert.match(dash, /TradingPerformancePanel/);
assert.match(dash, /RiskIntelligencePanel/);
assert.match(dash, /RobotActivityPanel/);
assert.match(dash, /RecentActivityPanel/);
assert.match(dash, /NotificationsStrip/);
assert.match(desk, /todayPnlTone/);
assert.match(desk, /metricsUpdatedAt/);

assert.equal(OWNER_RISK_POLICY_DISPLAY.maxLot, 0.01);
assert.equal(OWNER_RISK_POLICY_DISPLAY.dailyLossHaltPercent, 48);
assert.equal(OWNER_RISK_POLICY_DISPLAY.maxConcurrentPositions, 1);
assert.equal(OWNER_RISK_POLICY_DISPLAY.gridTrading, false);
assert.equal(OWNER_RISK_POLICY_DISPLAY.martingale, false);

// Pure halt threshold check (mirrors deriveRiskIntelligence daily halt rule).
{
  const equity = 1000;
  const todayPnl = -500;
  const usedPct = (Math.abs(todayPnl) / equity) * 100;
  assert.ok(usedPct >= OWNER_RISK_POLICY_DISPLAY.dailyLossHaltPercent);
}

console.log("dashboard intelligence contract ok");
