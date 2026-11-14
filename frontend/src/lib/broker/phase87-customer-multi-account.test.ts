/**
 * Phase 8.7 — multi-account panel remains available for ops contracts, but the
 * Broker Accounts customer page must not mount Multi-account status or a
 * separate Claim Ownership button (ownership attaches via Connect MT5 Account).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const panel = readFileSync(
  join(root, "components/broker/customer-multi-account-panel.tsx"),
  "utf8",
);
const workspace = readFileSync(
  join(root, "components/broker/broker-config-workspace.tsx"),
  "utf8",
);
const endpoints = readFileSync(join(root, "lib/api/endpoints.ts"), "utf8");
const catalog = readFileSync(join(root, "lib/broker/mt5-broker-catalog.ts"), "utf8");

assert.match(panel, /multiAccountOpsApi\.myDispatchStatus/);
assert.match(panel, /brokersApi\.accounts/);
assert.match(panel, /maskAccountNumber/);
assert.match(panel, /eligibility\.blocked/);
assert.match(panel, /blocked_reasons/);
assert.match(panel, /LIVE fan-out stays off/);
assert.equal(panel.includes("Worker Online"), false);
assert.equal(panel.includes("fake eligibility"), false);

// Customer Broker Accounts page: panel and Claim Ownership must be gone.
assert.equal(workspace.includes("CustomerMultiAccountPanel"), false);
assert.equal(workspace.includes("Claim ownership"), false);
assert.match(workspace, /Connect MT5 Account/);
assert.match(workspace, /Password is never displayed after submission/);
assert.doesNotMatch(workspace, /attaches ownership in one step/);

assert.match(endpoints, /myDispatchStatus/);
assert.match(endpoints, /\/multi-account\/dispatch\/status/);

// Canonical eight-broker order must remain product order (not alphabetical).
const order = [
  "weltrade",
  "xm",
  "exness",
  "hfm",
  "justmarkets",
  "ic-markets",
  "pepperstone",
  "fp-markets",
];
let last = -1;
for (const slug of order) {
  const idx = catalog.indexOf(`slug: "${slug}"`);
  assert.ok(idx > last, `catalog order missing or wrong for ${slug}`);
  last = idx;
}
assert.match(catalog, /logoSrc: "\/brand\/brokers\//);

console.log("phase87-customer-multi-account: ok");
