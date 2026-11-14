/**
 * Phase 4 AI Trading Intelligence frontend contracts.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");
const desk = readFileSync(
  join(root, "components/intelligence/phase4-ati-desk.tsx"),
  "utf8",
);
const page = readFileSync(
  join(root, "app/(app)/ai-trading-intelligence/page.tsx"),
  "utf8",
);
const riskCenter = readFileSync(
  join(root, "app/(app)/risk-center/page.tsx"),
  "utf8",
);
const freeze = readFileSync(
  join(root, "../../docs/production/PHASE4_AI_TRADING_INTELLIGENCE_FREEZE.md"),
  "utf8",
);

assert.match(endpoints, /aiTradingIntelligenceApi/);
assert.match(endpoints, /\/ai-trading-intelligence\/health/);
assert.match(endpoints, /\/ai-trading-intelligence\/supervisor/);
assert.match(desk, /MONITOR_ONLY/);
assert.match(desk, /not win probabilities/);
assert.doesNotMatch(desk, /guaranteed profit/i);
assert.match(page, /Phase4AtiDesk/);
assert.match(riskCenter, /aiTradingIntelligenceApi/);
assert.match(riskCenter, /AI risk alerts/);
assert.match(freeze, /MONITOR_ONLY/);
assert.match(freeze, /No auto-deploy/);

console.log("phase4-ati-contract: ok");
