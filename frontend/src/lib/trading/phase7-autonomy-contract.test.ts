/**
 * Phase 7 Autonomous Trading Control — contract smoke (no network).
 * Run: npx tsx src/lib/trading/phase7-autonomy-contract.test.ts
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(__dirname, "../..");

const pages = [
  "app/(app)/autonomous-trading/page.tsx",
  "app/(app)/autonomy-control/page.tsx",
  "app/(app)/decision-approvals/page.tsx",
  "app/(app)/trade-intelligence/page.tsx",
];

for (const p of pages) {
  assert.ok(existsSync(join(root, p)), `missing page ${p}`);
}

const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");
assert.match(endpoints, /autonomousTradingControlApi/);
assert.match(endpoints, /\/autonomous-trading-control\/health/);
assert.match(endpoints, /\/autonomous-trading-control\/execution\/authorize/);
assert.doesNotMatch(endpoints, /FORCE_FIRST_TRADE/);

const nav = readFileSync(join(root, "components/layout/nav-config.ts"), "utf8");
assert.match(nav, /"\/autonomous-trading"/);
assert.match(nav, /"\/autonomy-control"/);
assert.match(nav, /"\/decision-approvals"/);
assert.match(nav, /"\/trade-intelligence"/);

const desk = readFileSync(
  join(root, "components/ops/phase7/control-desk.tsx"),
  "utf8",
);
assert.match(desk, /OBSERVE_ONLY/);
assert.doesNotMatch(desk, /FORCE_FIRST_TRADE/);
assert.doesNotMatch(desk, /order_send\s*\(/);

const trading = readFileSync(
  join(root, "components/ops/phase7/trading-desk.tsx"),
  "utf8",
);
assert.match(trading, /never order_send|Never order_send/i);
assert.doesNotMatch(trading, /order_send\s*\(/);

console.log("phase7-autonomy-contract: ok");
