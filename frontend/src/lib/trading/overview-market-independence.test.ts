/**
 * Overview market chart must not require customer MT5 ownership.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const chart = readFileSync(join(root, "components/workspace/chart-panel.tsx"), "utf8");
const desk = readFileSync(
  join(root, "components/trading/overview-reference-desk.tsx"),
  "utf8",
);
const topbar = readFileSync(join(root, "components/layout/topbar.tsx"), "utf8");
const banner = readFileSync(join(root, "components/system/offline-banner.tsx"), "utf8");
const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");

assert.match(endpoints, /researchCandles/);
assert.match(endpoints, /researchTick/);
assert.match(endpoints, /\/mt5\/research\/candles\//);
assert.match(endpoints, /\/mt5\/research\/ticks\//);

assert.match(chart, /researchCandles/);
assert.match(chart, /marketFeedEnabled/);
assert.equal(chart.includes("Broker not connected"), false);
assert.equal(chart.includes("Connect MT5"), false);
assert.equal(chart.includes("enabled: connected"), false);

assert.match(desk, /Daily Risk/);
assert.match(desk, /marketLive/);
assert.match(desk, /brokerConnected/);
assert.equal(desk.includes("bar={"), false);

assert.equal(topbar.includes("Server time"), false);
assert.equal(topbar.includes("Server Time"), false);
assert.equal(topbar.includes("shell-tick"), false);
assert.equal(topbar.includes("Coins"), false);

assert.equal(banner.includes("API latency elevated"), false);

console.log("overview-market-independence: ok");
