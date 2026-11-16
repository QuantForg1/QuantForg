/**
 * Phase 3 household portfolio contracts — Book home, API client, honesty.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");
const nextCfg = readFileSync(join(root, "../next.config.ts"), "utf8");
const shell = readFileSync(join(root, "components/book/shell.tsx"), "utf8");
const desk = readFileSync(
  join(root, "components/book/household-desk.tsx"),
  "utf8",
);
const nav = readFileSync(join(root, "components/layout/nav-config.ts"), "utf8");
const riskCenter = readFileSync(
  join(root, "app/(app)/risk-center/page.tsx"),
  "utf8",
);

assert.match(endpoints, /householdPortfolioApi/);
assert.match(endpoints, /\/portfolio\/household/);
assert.match(endpoints, /\/portfolio\/household\/exposure/);
assert.match(endpoints, /\/portfolio\/household\/risk-check/);
assert.match(endpoints, /\/portfolio\/household\/attribution/);

assert.doesNotMatch(
  nextCfg,
  /source:\s*["']\/book["']\s*,\s*destination:\s*["']\/portfolio["']/,
);
assert.match(
  nextCfg,
  /source:\s*["']\/portfolio["']\s*,\s*destination:\s*["']\/book["']/,
);

assert.match(shell, /HouseholdDesk/);
// Missing figures render as "—", never as invented zeros.
assert.match(desk, /show “—” until the broker reports them/);
assert.match(desk, /data_status/);
assert.match(desk, /Export CSV/);

assert.match(nav, /"\/book"/);
assert.match(nav, /label:\s*"Book"/);

assert.match(riskCenter, /householdPortfolioApi/);
assert.match(riskCenter, /householdRisk\.allowed/);

console.log("phase3-household-contract: ok");

// Book layout: content-sized sections in one scroll area (no stretched rows
// that leave large empty gaps when a panel has little data).
assert.doesNotMatch(shell, /grid-rows-\[auto_auto_minmax/);
assert.doesNotMatch(shell, /max-h-\[38%\]/);
assert.match(shell, /overflow-y-auto overflow-x-hidden/);
console.log("book layout contract ok");
