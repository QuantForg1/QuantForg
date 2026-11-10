/**
 * Phase 4 contracts: Overview cleanup + Risk Center owner-policy isolation.
 * Run: node --experimental-strip-types src/lib/dashboard/phase4-risk-center.test.ts
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const dash = readFileSync(join(root, "app/(app)/dashboard/page.tsx"), "utf8");
const riskCenter = readFileSync(join(root, "app/(app)/risk-center/page.tsx"), "utf8");
const riskPanel = readFileSync(
  join(root, "components/trading/dashboard-intelligence/risk-intelligence-panel.tsx"),
  "utf8",
);
const riskIntel = readFileSync(join(root, "lib/dashboard/risk-intelligence.ts"), "utf8");
const ownerSummary = readFileSync(
  join(root, "components/execution/owner-policy-summary.tsx"),
  "utf8",
);
const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");
assert.match(dash, /TradingPerformancePanel/);
assert.match(dash, /OverviewReferenceDesk/);
assert.doesNotMatch(dash, /RiskIntelligencePanel/);
assert.doesNotMatch(dash, /RobotActivityPanel/);
assert.doesNotMatch(dash, /NotificationsStrip/);
assert.doesNotMatch(dash, /RecentActivityPanel/);
assert.doesNotMatch(dash, /OWNER_RISK_POLICY_DISPLAY/);

assert.match(riskCenter, /My Risk Preferences/);
assert.match(riskCenter, /Risk Protection Status/);
assert.match(riskCenter, /Risk History/);
assert.match(riskCenter, /riskApi\.preferences/);
assert.doesNotMatch(riskCenter, /OwnerPolicySummary/);
assert.doesNotMatch(riskCenter, /Owner policy \(read-only\)/);

assert.doesNotMatch(riskPanel, /Owner policy \(read-only\)/);
assert.doesNotMatch(riskPanel, /Max lot \{policy\.maxLot\}/);
assert.match(riskIntel, /platform daily-loss protection|effective protection limits/);
assert.doesNotMatch(riskIntel, /Within owner risk ceilings/);

assert.match(ownerSummary, /\/admin\/control\/overview/);
assert.match(endpoints, /\/risk\/preferences/);
assert.match(endpoints, /updatePreferences/);

console.log("phase4 risk center contract ok");
