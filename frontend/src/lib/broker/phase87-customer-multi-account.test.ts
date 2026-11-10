/**
 * Phase 8.7 — customer multi-account panel contracts (no fabricated eligibility).
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

assert.match(panel, /multiAccountOpsApi\.myDispatchStatus/);
assert.match(panel, /brokersApi\.accounts/);
assert.match(panel, /maskAccountNumber/);
assert.match(panel, /eligibility\.blocked/);
assert.match(panel, /blocked_reasons/);
assert.match(panel, /LIVE fan-out stays off/);
assert.equal(panel.includes("Worker Online"), false);
assert.equal(panel.includes("fake eligibility"), false);
assert.match(workspace, /CustomerMultiAccountPanel/);
assert.match(endpoints, /myDispatchStatus/);
assert.match(endpoints, /\/multi-account\/dispatch\/status/);

console.log("phase87-customer-multi-account: ok");
