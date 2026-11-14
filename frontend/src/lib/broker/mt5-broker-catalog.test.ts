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
  brokerTradingReadinessDisplayLabel,
  brokerVerificationDisplayLabel,
  brokerVerificationStatusCode,
} from "./mt5-broker-catalog.ts";

assert.equal(MT5_BROKER_OPTIONS.length, 8);
assert.deepEqual(
  MT5_BROKER_OPTIONS.map((b) => b.slug),
  [
    "weltrade",
    "xm",
    "exness",
    "hfm",
    "justmarkets",
    "ic-markets",
    "pepperstone",
    "fp-markets",
  ],
);
assert.equal(brokerBySlug("weltrade")?.connectable, true);
assert.equal(brokerBySlug("weltrade")?.connectionStatus, "production_verified");
assert.equal(brokerBySlug("exness")?.connectable, true);
assert.equal(brokerBySlug("exness")?.connectionStatus, "live_verified");
assert.equal(brokerBySlug("exness")?.customerSelectable, true);
assert.equal(brokerBySlug("justmarkets")?.name, "JustMarkets");
assert.equal(brokerBySlug("justmarkets")?.customerSelectable, true);
assert.equal(brokerBySlug("justmarkets")?.connectable, true);
assert.equal(brokerBySlug("justmarkets")?.connectionStatus, "live_verified");
assert.equal(brokerBySlug("hfm")?.connectionStatus, "live_verified");
assert.equal(brokerBySlug("hfm")?.connectable, true);
assert.ok(brokerBySlug("hfm")?.servers.live.includes("HFMarketsGlobal-Live20"));
assert.equal(brokerBySlug("ic-markets")?.connectionStatus, "live_verified");
assert.equal(brokerBySlug("fp-markets")?.connectionStatus, "live_verified");
assert.equal(
  MT5_BROKER_OPTIONS.filter((b) =>
    ["live_verified", "production_verified"].includes(b.connectionStatus),
  ).length,
  8,
);
assert.ok(MT5_BROKER_OPTIONS.every((b) => b.connectable === true));
assert.ok(MT5_BROKER_OPTIONS.every((b) => b.customerSelectable));
assert.equal(matchBrokerByServer("Weltrade-Real")?.slug, "weltrade");
assert.equal(matchBrokerByServer("JustMarkets-Live2")?.slug, "justmarkets");

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
// Documented observed LIVE server may appear before full VERIFIED_LIVE connectable.
assert.ok(exnessRows.some((r) => r.name === "Exness-MT5Real10" && r.environment === "live"));
assert.ok(exnessRows.every((r) => r.confirmed === false || r.evidence_classification === "DOCUMENTED" || r.evidence_classification === "CONFIRMED"));

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
    connection_status: "live_verified",
    verification_status: "VERIFIED_LIVE",
    display_label: "Verified",
    connectable: true,
  },
  {
    slug: "xm",
    connection_status: "demo_verified",
    connectable: true,
  },
  {
    slug: "hfm",
    connection_status: "owner_verified_live",
    connectable: true,
  },
]);
assert.equal(mapped.find((b) => b.slug === "weltrade")?.connectable, true);
assert.equal(mapped.find((b) => b.slug === "exness")?.connectable, true);
assert.equal(mapped.find((b) => b.slug === "exness")?.connectionStatus, "live_verified");
assert.equal(mapped.find((b) => b.slug === "hfm")?.connectionStatus, "live_verified");
assert.equal(mapped.find((b) => b.slug === "hfm")?.connectable, true);
assert.equal(mapped.find((b) => b.slug === "xm")?.connectionStatus, "demo_verified");
assert.equal(mapped.find((b) => b.slug === "xm")?.connectable, true);

assert.equal(brokerVerificationDisplayLabel("live_verified"), "Verified");
assert.equal(brokerVerificationDisplayLabel("owner_verified_live"), "Verified");
assert.equal(brokerVerificationStatusCode("live_verified"), "VERIFIED_LIVE");
assert.notEqual(brokerVerificationDisplayLabel("live_verified"), "FUNDING_REQUIRED");
assert.equal(
  brokerTradingReadinessDisplayLabel({
    verification_status: "VERIFIED_LIVE",
    trading_readiness: "FUNDING_REQUIRED",
  }),
  "Verified",
);
assert.equal(
  brokerTradingReadinessDisplayLabel({
    trading_readiness_display: "Verified",
    trading_readiness: "AUTH_OK_TRADE_NOT_ENABLED",
  }),
  "Verified",
);

for (const broker of MT5_BROKER_OPTIONS) {
  assert.ok(broker.logoSrc.startsWith("/brand/brokers/"));
  assert.equal(broker.connectable, true);
}

console.log("mt5-broker-catalog: ok");
