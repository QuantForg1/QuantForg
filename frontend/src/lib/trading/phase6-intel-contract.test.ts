/**
 * Phase 6 Institutional Intelligence — contract smoke (no network).
 * Run: npx tsx src/lib/trading/phase6-intel-contract.test.ts
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(__dirname, "../..");

const pages = [
  "app/(app)/intelligence-center/page.tsx",
  "app/(app)/predictive-market-intelligence/page.tsx",
  "app/(app)/strategy-analytics/page.tsx",
  "app/(app)/predictive-risk/page.tsx",
  "app/(app)/portfolio-optimization/page.tsx",
  "app/(app)/execution-optimization/page.tsx",
  "app/(app)/decision-intelligence/page.tsx",
  "app/(app)/institutional-reports/page.tsx",
];

for (const p of pages) {
  assert.ok(existsSync(join(root, p)), `missing page ${p}`);
}

const decision = readFileSync(
  join(root, "app/(app)/decision-intelligence/page.tsx"),
  "utf8",
);
assert.match(decision, /Phase6DecisionDesk/);
assert.match(decision, /DecisionIntelligenceWorkspace/);

const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");
assert.match(endpoints, /institutionalIntelligenceApi/);
assert.match(endpoints, /\/institutional-intelligence\/health/);
assert.match(endpoints, /\/institutional-intelligence\/market\/overview/);
assert.match(endpoints, /\/institutional-intelligence\/decision\/recommendations/);

const nav = readFileSync(join(root, "components/layout/nav-config.ts"), "utf8");
assert.match(nav, /"\/intelligence-center"/);
assert.match(nav, /"\/predictive-market-intelligence"/);
assert.match(nav, /"\/execution-optimization"/);

const desk = readFileSync(
  join(root, "components/ops/phase6/decision-desk.tsx"),
  "utf8",
);
assert.match(desk, /Approved ≠ LIVE|Approved never/);
assert.doesNotMatch(desk, /FORCE_FIRST_TRADE/);
assert.doesNotMatch(desk, /order_send\s*\(/);

console.log("phase6-intel-contract: ok");
