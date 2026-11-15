/**
 * Phase 8 Quantitative Research Control — contract smoke (no network).
 * Run: npx tsx src/lib/trading/phase8-research-contract.test.ts
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(__dirname, "../..");

const pages = [
  "app/(app)/quant-research/page.tsx",
  "app/(app)/strategy-factory/page.tsx",
  "app/(app)/research-data/page.tsx",
  "app/(app)/strategy-backtesting/page.tsx",
  "app/(app)/strategy-optimization/page.tsx",
  "app/(app)/research-leaderboard/page.tsx",
  "app/(app)/research-governance/page.tsx",
];

for (const p of pages) {
  assert.ok(existsSync(join(root, p)), `missing page ${p}`);
}

const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");
assert.match(endpoints, /quantitativeResearchControlApi/);
assert.match(endpoints, /\/quantitative-research-control\/health/);
assert.match(endpoints, /\/quantitative-research-control\/strategy\/ai\/hypothesize/);
assert.match(endpoints, /\/quantitative-research-control\/validation\/pipeline/);
assert.doesNotMatch(endpoints, /FORCE_FIRST_TRADE/);

const nav = readFileSync(join(root, "components/layout/nav-config.ts"), "utf8");
assert.match(nav, /"\/quant-research"/);
assert.match(nav, /"\/strategy-factory"/);
assert.match(nav, /"\/research-data"/);
assert.match(nav, /"\/strategy-backtesting"/);
assert.match(nav, /"\/strategy-optimization"/);
assert.match(nav, /"\/research-leaderboard"/);
assert.match(nav, /"\/research-governance"/);

const desks = [
  "components/ops/phase8/hub-desk.tsx",
  "components/ops/phase8/factory-desk.tsx",
  "components/ops/phase8/data-desk.tsx",
  "components/ops/phase8/backtest-desk.tsx",
  "components/ops/phase8/optimize-desk.tsx",
  "components/ops/phase8/leaderboard-desk.tsx",
  "components/ops/phase8/governance-desk.tsx",
];

for (const d of desks) {
  const src = readFileSync(join(root, d), "utf8");
  assert.doesNotMatch(src, /order_send\s*\(/);
  assert.doesNotMatch(src, /FORCE_FIRST_TRADE/);
}

const hub = readFileSync(join(root, "components/ops/phase8/hub-desk.tsx"), "utf8");
assert.match(hub, /never order_send|Never order_send/i);
assert.match(hub, /quantforg-strategy-factory/);
assert.match(hub, /autonomous-trading/);

console.log("phase8-research-contract: ok");
