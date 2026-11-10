/**
 * Broker Accounts redesign contracts — selector parity, honest catalogue, Weltrade path.
 */
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  MT5_BROKER_OPTIONS,
  brokerBySlug,
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
{
  const idx = workspace.indexOf("const onBrokerPicked");
  assert.ok(idx > 0);
  const block = workspace.slice(idx, idx + 220);
  assert.match(block, /setServer\(""\)/);
  assert.match(block, /setBrokerSwitchEpoch/);
}
assert.match(workspace, /setServer\(""\)/);
assert.match(workspace, /serversLoading/);
assert.match(workspace, /No verified MT5 servers/);
assert.match(workspace, /will not be substituted/);
assert.match(workspace, /Demo and Live are not interchangeable/);
assert.match(workspace, /weltradeApi\.connect/);
assert.match(workspace, /weltradeApi\.claim/);
assert.match(workspace, /Password is never displayed after submission/);

for (const broker of MT5_BROKER_OPTIONS) {
  const asset = join(root, "..", "public", broker.logoSrc.replace(/^\//, ""));
  assert.ok(existsSync(asset), `missing logo asset for ${broker.slug}: ${broker.logoSrc}`);
}

const weltrade = brokerBySlug("weltrade");
assert.ok(weltrade?.connectable);
const rows = serverRowsForBroker(weltrade);
assert.deepEqual(
  rows.map((r) => r.name).sort(),
  ["Weltrade-Demo", "Weltrade-Real"].sort(),
);

for (const pending of MT5_BROKER_OPTIONS.filter((b) => !b.connectable)) {
  assert.equal(serverRowsForBroker(pending).length, 0);
  assert.equal(pending.connectable, false);
}

console.log("broker-accounts-redesign: ok");
