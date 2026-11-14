/**
 * Phase 5 Control Center — contract smoke (no network).
 * Run: npx tsx src/lib/trading/phase5-ops-contract.test.ts
 */
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const root = join(__dirname, "../..");

const pages = [
  "app/(app)/operations/page.tsx",
  "app/(app)/strategy-lifecycle/page.tsx",
  "app/(app)/execution-intelligence/page.tsx",
  "app/(app)/account-orchestration/page.tsx",
  "app/(app)/risk-automation/page.tsx",
  "app/(app)/incident-center/page.tsx",
  "app/(app)/governance/page.tsx",
];

for (const p of pages) {
  const full = join(root, p);
  assert.ok(existsSync(full), `missing page ${p}`);
}

const redirect = readFileSync(
  join(root, "app/(app)/execution-intel/page.tsx"),
  "utf8",
);
assert.match(redirect, /redirect\("\/execution-intelligence"\)/);

const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");
assert.match(endpoints, /institutionalOpsApi/);
assert.match(endpoints, /\/institutional-ops\/health/);
assert.match(endpoints, /\/institutional-ops\/operations\/overview/);
assert.match(endpoints, /\/institutional-ops\/strategy-lifecycle\/overview/);
assert.match(endpoints, /\/institutional-ops\/execution\/overview/);
assert.match(endpoints, /\/institutional-ops\/accounts\/overview/);
assert.match(endpoints, /\/institutional-ops\/risk\/overview/);
assert.match(endpoints, /\/institutional-ops\/incidents\/overview/);
assert.match(endpoints, /\/institutional-ops\/governance\/summary/);

const nav = readFileSync(
  join(root, "components/layout/nav-config.ts"),
  "utf8",
);
assert.match(nav, /"\/operations"/);
assert.match(nav, /"\/strategy-lifecycle"/);
assert.match(nav, /"\/execution-intelligence"/);
assert.match(nav, /"\/account-orchestration"/);
assert.match(nav, /"\/risk-automation"/);
assert.match(nav, /"\/incident-center"/);
assert.match(nav, /"\/governance"/);

const opsDesk = readFileSync(
  join(root, "components/ops/phase5/operations-desk.tsx"),
  "utf8",
);
assert.match(opsDesk, /startRobot/);
assert.match(opsDesk, /pauseRobot/);
assert.match(opsDesk, /stopRobot/);
assert.match(opsDesk, /Confirm stop/);
assert.match(opsDesk, /never_order_send/);
assert.doesNotMatch(opsDesk, /FORCE_FIRST_TRADE/);
assert.doesNotMatch(opsDesk, /order_send\s*\(/);

console.log("phase5-ops-contract: ok");
