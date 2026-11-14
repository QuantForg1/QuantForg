/**
 * Broker Accounts 2.0 — premium minimal connect form contracts.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  MT5_BROKER_OPTIONS,
  brokerBySlug,
  connectionLifecycleLabel,
  mapRegistryBrokers,
  serverRowsForBroker,
} from "./mt5-broker-catalog.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const workspace = readFileSync(
  join(root, "components/broker/broker-config-workspace.tsx"),
  "utf8",
);

assert.equal(workspace.includes("Search verified servers"), false);
assert.match(workspace, /function ServerSelect/);
assert.match(workspace, /function BrokerSelect/);
assert.match(workspace, /FieldShell/);
assert.match(workspace, /h-12 w-full/);
assert.match(workspace, /onBrokerPicked/);
assert.match(workspace, /broker_slug: selectedBroker\.slug/);
assert.match(workspace, /Or paste exact portal server name/);
assert.match(workspace, /BrokerSelect/);
assert.doesNotMatch(
  workspace.slice(
    workspace.indexOf("function BrokerSelect"),
    workspace.indexOf("function ServerSelect"),
  ),
  /Pending|Verified/,
);
assert.match(workspace, /weltradeApi\.connect/);
assert.match(workspace, /Password is never displayed after submission/);

// Broker Page 2.0 — remove customer-facing noise.
assert.doesNotMatch(workspace, /Account type/);
assert.doesNotMatch(workspace, /LIVE is primary/);
assert.doesNotMatch(workspace, /Connection status/);
assert.doesNotMatch(workspace, /function EnvBadge/);
assert.doesNotMatch(workspace, /function ConfirmedBadge/);
assert.doesNotMatch(workspace, /function SecurityFooter/);
assert.doesNotMatch(workspace, /AES-256/);
assert.doesNotMatch(workspace, /Official MetaTrader 5 · LIVE connect/);
assert.doesNotMatch(workspace, />Confirmed</);
assert.doesNotMatch(workspace, />Candidate</);
assert.match(workspace, /useVirtualWindow/);
assert.match(workspace, /Search MT5 servers/);

{
  const idx = workspace.indexOf("const onBrokerPicked");
  assert.ok(idx > 0);
  const block = workspace.slice(idx, idx + 320);
  assert.match(block, /setServer\(""\)/);
  assert.match(block, /setBrokerSwitchEpoch/);
}

for (const broker of MT5_BROKER_OPTIONS) {
  const asset = join(root, "..", "public", broker.logoSrc.replace(/^\//, ""));
  assert.ok(existsSync(asset), `missing logo asset for ${broker.slug}: ${broker.logoSrc}`);
  assert.equal(broker.customerSelectable, true);
}

assert.equal(MT5_BROKER_OPTIONS.length, 8);
assert.equal(connectionLifecycleLabel("not_connected"), "Not Connected");
assert.equal(connectionLifecycleLabel("connected"), "Connected");

const weltrade = brokerBySlug("weltrade");
assert.ok(weltrade?.connectable);
const rows = serverRowsForBroker(weltrade);
assert.deepEqual(
  rows.map((r) => r.name).sort(),
  ["Weltrade-Demo", "Weltrade-Real"].sort(),
);

const mapped = mapRegistryBrokers([
  { slug: "xm", connection_status: "demo_verified", connectable: true, customer_selectable: true },
  { slug: "exness", connection_status: "live_verified", connectable: true, customer_selectable: true },
]);
assert.equal(mapped.find((b) => b.slug === "xm")?.customerSelectable, true);
assert.equal(mapped.find((b) => b.slug === "exness")?.customerSelectable, true);

console.log("broker-accounts-redesign: ok");
