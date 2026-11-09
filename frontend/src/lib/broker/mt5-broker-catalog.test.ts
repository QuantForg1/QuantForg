/**
 * Broker Accounts catalog — verified vs documented brands.
 */
import assert from "node:assert/strict";
import {
  MT5_BROKER_OPTIONS,
  matchBrokerByServer,
  serversForBroker,
  brokerBySlug,
  mapRegistryBrokers,
} from "./mt5-broker-catalog.ts";

assert.ok(MT5_BROKER_OPTIONS.length >= 7);
assert.equal(brokerBySlug("weltrade")?.connectable, true);
assert.equal(brokerBySlug("weltrade")?.connectionStatus, "production_verified");
assert.equal(brokerBySlug("exness")?.connectable, false);
assert.equal(brokerBySlug("hfm")?.servers.live.length, 0);
assert.equal(matchBrokerByServer("Weltrade-Real")?.slug, "weltrade");

const weltradeLive = serversForBroker(brokerBySlug("weltrade"), "live");
assert.ok(weltradeLive.includes("Weltrade-Real"));

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
]);
assert.equal(mapped.find((b) => b.slug === "weltrade")?.connectable, true);
assert.equal(mapped.find((b) => b.slug === "exness")?.connectable, false);

for (const broker of MT5_BROKER_OPTIONS) {
  assert.ok(broker.logoSrc.startsWith("/brand/brokers/"));
  if (!broker.connectable) {
    assert.equal(broker.servers.live.length, 0);
    assert.equal(broker.servers.demo.length, 0);
  }
}

console.log("mt5-broker-catalog: ok");
