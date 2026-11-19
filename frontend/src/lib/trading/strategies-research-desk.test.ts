/**
 * Strategies and Research are one desk. Legacy /research opens /strategy.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const nav = readFileSync(join(root, "components/layout/nav-config.ts"), "utf8");
const page = readFileSync(join(root, "app/(app)/strategy/page.tsx"), "utf8");
const research = readFileSync(join(root, "app/(app)/research/page.tsx"), "utf8");
const desk = readFileSync(join(root, "components/strategies/strategies-research-desk.tsx"), "utf8");
const nextConfig = readFileSync(join(root, "../next.config.ts"), "utf8");

assert.match(page, /StrategiesResearchDesk/);
assert.match(desk, /Strategies &amp; Research/);
assert.match(desk, /strategyApi\.engineRun/);
assert.match(desk, /strategyApi\.evaluate/);
assert.match(desk, /researchLabApi\.validate/);
assert.match(desk, /researchLabApi\.promote/);
assert.match(desk, /backtestApi\.run/);
assert.match(desk, /walkforwardApi\.run/);
assert.match(desk, /researchLabApi\.report/);
assert.match(desk, /items-stretch/);
assert.match(desk, /Not available/);
assert.match(desk, /does not place an order/);
assert.match(desk, /does not activate live trading/);
assert.doesNotMatch(desk, /order_send|placeOrder|close_position/);
assert.match(research, /redirect\("\/strategy"\)/);
assert.match(nextConfig, /source:\s*"\/research",\s*destination:\s*"\/strategy"/);
assert.match(nav, /label: "Strategies & Research"/);
assert.equal(/label: "Strategies"[,}]/.test(nav), false);
const order = nav.slice(nav.indexOf("export const TRADER_DESK_ORDER"), nav.indexOf("export const OPERATOR_RAIL_ORDER"));
assert.match(order, /"\/strategy"/);
assert.equal(order.includes('"/research"'), false);

console.log("strategies-research-desk: ok");
