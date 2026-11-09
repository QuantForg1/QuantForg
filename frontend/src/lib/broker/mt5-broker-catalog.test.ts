/**
 * Broker Accounts catalog — documented MT5 brands + server hints only.
 */
import assert from "node:assert/strict";
import {
  MT5_BROKER_OPTIONS,
  matchBrokerByServer,
  serversForBroker,
  brokerBySlug,
} from "./mt5-broker-catalog.ts";

assert.ok(MT5_BROKER_OPTIONS.length >= 7);
assert.equal(brokerBySlug("weltrade")?.name, "Weltrade");
assert.equal(matchBrokerByServer("Weltrade-Real")?.slug, "weltrade");
assert.equal(matchBrokerByServer("Exness-MT5Real")?.slug, "exness");
assert.equal(matchBrokerByServer("ICMarketsSC-MT5")?.slug, "ic-markets");
assert.equal(matchBrokerByServer("Pepperstone-MT5-Live")?.slug, "pepperstone");
assert.equal(matchBrokerByServer("XMGlobal-MT5")?.slug, "xm");
assert.equal(matchBrokerByServer("HFM-Live")?.slug, "hfm");
assert.equal(matchBrokerByServer("FPMarkets-Live")?.slug, "fp-markets");

const weltradeLive = serversForBroker(brokerBySlug("weltrade"), "live");
assert.ok(weltradeLive.includes("Weltrade-Real"));

for (const broker of MT5_BROKER_OPTIONS) {
  assert.ok(broker.logoSrc.startsWith("/brand/brokers/"));
  assert.ok(broker.servers.live.length > 0);
  assert.ok(broker.servers.demo.length > 0);
}

console.log("mt5-broker-catalog: ok");
