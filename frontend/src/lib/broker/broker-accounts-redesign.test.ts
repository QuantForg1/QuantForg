/**
 * Broker Accounts LIVE-first redesign contracts.
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
assert.match(workspace, /setAccountType\("live"\)/);
assert.match(workspace, /broker_slug: selectedBroker\.slug/);
assert.match(workspace, /Or paste exact portal server name/);
assert.match(workspace, /connectionLifecycleLabel/);
assert.match(workspace, /connection_failed/);
// Selector must not show Pending/Verified badges (connection lifecycle replaces them).
assert.equal(/["']Verified["']/.test(workspace), false);
assert.equal(/["']Pending["']/.test(workspace), false);
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
assert.match(workspace, /LIVE is primary/);

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
  { slug: "exness", connection_status: "not_verified", connectable: false, customer_selectable: true },
]);
assert.equal(mapped.find((b) => b.slug === "xm")?.customerSelectable, true);
assert.equal(mapped.find((b) => b.slug === "exness")?.customerSelectable, true);

console.log("broker-accounts-redesign: ok");
