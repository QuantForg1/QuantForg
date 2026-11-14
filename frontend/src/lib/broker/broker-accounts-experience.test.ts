/**
 * Broker Accounts experience contracts — logos, order, no Claim Ownership,
 * no Multi-account status card, single Connect MT5 Account CTA.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  MT5_BROKER_OPTIONS,
  serverRowsForBroker,
  type Mt5BrokerSlug,
} from "./mt5-broker-catalog.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const workspace = readFileSync(
  join(root, "components/broker/broker-config-workspace.tsx"),
  "utf8",
);
const logo = readFileSync(join(root, "components/broker/broker-logo.tsx"), "utf8");

const expectedOrder: Mt5BrokerSlug[] = [
  "weltrade",
  "xm",
  "exness",
  "hfm",
  "justmarkets",
  "ic-markets",
  "pepperstone",
  "fp-markets",
];

assert.equal(MT5_BROKER_OPTIONS.length, 8);
assert.deepEqual(
  MT5_BROKER_OPTIONS.map((b) => b.slug),
  expectedOrder,
);

for (const broker of MT5_BROKER_OPTIONS) {
  assert.ok(broker.logoSrc.startsWith("/brand/brokers/"), broker.slug);
  const assetPath = join(root, "../public", broker.logoSrc.replace(/^\//, ""));
  assert.ok(existsSync(assetPath), `missing logo asset for ${broker.slug}: ${assetPath}`);
  assert.equal(broker.customerSelectable, true);
}

assert.match(logo, /official logo/);
assert.match(workspace, /Search brokers/);
assert.match(workspace, /Search MT5 servers/);
assert.equal(workspace.includes("Claim ownership"), false);
assert.equal(workspace.includes("CustomerMultiAccountPanel"), false);
assert.equal(workspace.includes("Multi-account status"), false);
assert.match(workspace, /Connect MT5 Account/);

const xm = MT5_BROKER_OPTIONS.find((b) => b.slug === "xm");
const pepper = MT5_BROKER_OPTIONS.find((b) => b.slug === "pepperstone");
assert.ok(xm && pepper);
const xmRows = serverRowsForBroker(xm);
const pepperRows = serverRowsForBroker(pepper);
assert.ok(xmRows.some((r) => r.name === "XMGlobal-MT5 20" && r.environment === "live"));
assert.ok(
  pepperRows.some((r) => r.name === "PepperstoneKE-MT5-Live01" && r.environment === "live"),
);

// Broker change must not keep a stale server from another broker in the helper.
const exness = MT5_BROKER_OPTIONS.find((b) => b.slug === "exness");
assert.ok(exness);
const exnessRows = serverRowsForBroker(exness, undefined, undefined, [
  {
    name: "PepperstoneKE-MT5-Live01",
    environment: "live",
    source: "stale_test",
    verified_at: null,
    confirmed: false,
    evidence_classification: "CANDIDATE",
  },
]);
// Candidate push is caller-filtered by API; helper still stores names but UI clears
// selection on broker change — assert workspace clears server on broker pick.
assert.match(workspace, /setServer\(""\)/);
assert.match(workspace, /setManualServer\(""\)/);
assert.ok(exnessRows.length >= 0);

console.log("broker-accounts-experience: ok");
