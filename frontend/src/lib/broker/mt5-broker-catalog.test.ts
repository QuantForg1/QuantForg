/**
 * Broker Accounts catalog — verified vs documented brands.
 */
import assert from "node:assert/strict";
import {
  MT5_BROKER_OPTIONS,
  matchBrokerByServer,
  serversForBroker,
  serverRowsForBroker,
  classifyServerEnvironment,
  brokerBySlug,
  mapRegistryBrokers,
} from "./mt5-broker-catalog.ts";

assert.ok(MT5_BROKER_OPTIONS.length >= 7);
assert.equal(brokerBySlug("weltrade")?.connectable, true);
assert.equal(brokerBySlug("weltrade")?.connectionStatus, "production_verified");
assert.equal(brokerBySlug("exness")?.connectable, false);
assert.equal(brokerBySlug("exness")?.customerSelectable, true);
assert.equal(brokerBySlug("hfm")?.servers.live.length, 0);
assert.ok(MT5_BROKER_OPTIONS.every((b) => b.customerSelectable));
assert.equal(matchBrokerByServer("Weltrade-Real")?.slug, "weltrade");

const weltradeLive = serversForBroker(brokerBySlug("weltrade"), "live");
assert.ok(weltradeLive.includes("Weltrade-Real"));
assert.ok(!weltradeLive.includes("Weltrade-Demo"));

const weltradeDemo = serversForBroker(brokerBySlug("weltrade"), "demo");
assert.ok(weltradeDemo.includes("Weltrade-Demo"));

const weltradeRows = serverRowsForBroker(brokerBySlug("weltrade"));
assert.ok(weltradeRows.some((r) => r.name === "Weltrade-Real" && r.environment === "live"));
assert.ok(weltradeRows.some((r) => r.name === "Weltrade-Demo" && r.environment === "demo"));

assert.equal(classifyServerEnvironment("Weltrade-Real"), "live");
assert.equal(classifyServerEnvironment("Weltrade-Demo"), "demo");
assert.equal(classifyServerEnvironment(""), "unknown");
assert.equal(classifyServerEnvironment("XMGlobal-MT5"), "unknown");
assert.equal(classifyServerEnvironment("Exness-MT5Trial9"), "demo");

const exnessRows = serverRowsForBroker(brokerBySlug("exness"), undefined, []);
assert.equal(exnessRows.length, 0);

const apiOnly = serverRowsForBroker(brokerBySlug("exness"), undefined, [
  {
    name: "Exness-MT5Trial",
    environment: "demo",
    source: "windows_mt5_demo_verify",
    verified_at: "2026-11-09T00:00:00+00:00",
  },
]);
assert.equal(apiOnly.length, 1);
assert.equal(apiOnly[0]?.name, "Exness-MT5Trial");

// Switching brokers must not keep foreign servers in the catalogue helper.
const pepperstone = serverRowsForBroker(brokerBySlug("pepperstone"), undefined, [
  {
    name: "Pepperstone-Demo",
    environment: "demo",
    source: "evidence",
    verified_at: "2026-11-09T00:00:00+00:00",
  },
]);
assert.ok(!pepperstone.some((r) => r.name.includes("Weltrade")));
assert.ok(!pepperstone.some((r) => r.name.includes("Exness")));

const mapped = mapRegistryBrokers([
  {
    slug: "weltrade",
    connection_status: "production_verified",
    connectable: true,
  },
  {
    slug: "exness",
    connection_status: "not_verified",
    connectable: false,
  },
  {
    slug: "xm",
    connection_status: "demo_verified",
    connectable: true,
  },
]);
assert.equal(mapped.find((b) => b.slug === "weltrade")?.connectable, true);
assert.equal(mapped.find((b) => b.slug === "exness")?.connectable, false);
assert.equal(mapped.find((b) => b.slug === "xm")?.connectionStatus, "demo_verified");
assert.equal(mapped.find((b) => b.slug === "xm")?.connectable, true);

for (const broker of MT5_BROKER_OPTIONS) {
  assert.ok(broker.logoSrc.startsWith("/brand/brokers/"));
  if (!broker.connectable) {
    assert.equal(broker.servers.live.length, 0);
    assert.equal(broker.servers.demo.length, 0);
  }
}

console.log("mt5-broker-catalog: ok");
