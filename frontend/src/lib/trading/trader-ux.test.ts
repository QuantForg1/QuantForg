/**
 * Phase 49 trader UX — connection labels, unavailable vs empty, error copy.
 * Run: node --experimental-strip-types src/lib/trading/trader-ux.test.ts
 */
import assert from "node:assert/strict";
import {
  isLiveBrokerCatalogue,
  marketDataState,
  mergeCatalogueRows,
  resolveConnectionPresentation,
  scoreDisplay,
  traderFacingErrorMessage,
} from "./trader-ux.ts";

{
  const view = resolveConnectionPresentation({});
  assert.equal(view.label, "…");
  assert.notEqual(view.state, "BROKER_NOT_CONNECTED");
}

{
  const view = resolveConnectionPresentation({ ux_state: "NO_BROKER", broker: "Disconnected" });
  assert.equal(view.state, "BROKER_NOT_CONNECTED");
  assert.equal(view.label, "BROKER NOT CONNECTED");
  assert.equal(view.liveBrokerCatalogue, false);
}

{
  const view = resolveConnectionPresentation(
    { ux_state: "NO_BROKER", broker: "Disconnected" },
    { connecting: true },
  );
  assert.equal(view.state, "CONNECTING");
  assert.equal(view.label, "CONNECTING");
}

{
  const view = resolveConnectionPresentation({
    ux_state: "SESSION_MISMATCH",
    broker: "Connected",
    session_code: "ACCOUNT_SESSION_MISMATCH",
    account: "16••06",
    server: "Wel***eal",
  });
  assert.equal(view.state, "ACCOUNT_SESSION_MISMATCH");
  assert.equal(view.connected, false);
}

{
  const view = resolveConnectionPresentation({
    ux_state: "ROBOT_READY",
    broker: "Connected",
    connection: "Healthy",
    account: "16••06",
    server: "Wel***eal",
    last_verified: "2026-08-29T10:00:00+00:00",
    catalogue_source: "LIVE_BROKER",
    catalogue_unavailable: false,
  });
  assert.equal(view.state, "CONNECTED");
  assert.equal(view.label, "CONNECTED");
  assert.equal(view.liveBrokerCatalogue, true);
  assert.equal(view.maskedLogin, "16••06");
}

{
  const view = resolveConnectionPresentation({
    ux_state: "CATALOGUE_UNAVAILABLE",
    broker: "Connected",
    catalogue_unavailable: true,
    catalogue_source: "UNAVAILABLE",
    account: "16••06",
    server: "Wel***eal",
    connection: "Healthy",
  });
  assert.equal(view.state, "CATALOGUE_UNAVAILABLE");
  assert.equal(view.label, "CONNECTED");
  assert.equal(view.catalogueUnavailable, true);
  assert.equal(view.liveBrokerCatalogue, false);
}

assert.equal(isLiveBrokerCatalogue({ catalogue_source: "LIVE_BROKER", catalogue_unavailable: false }), true);
assert.equal(isLiveBrokerCatalogue({ catalogue_source: "INJECTED", catalogue_unavailable: false }), false);
assert.equal(isLiveBrokerCatalogue({ catalogue_source: "LIVE_BROKER", catalogue_unavailable: true }), false);

assert.equal(scoreDisplay(null), "UNKNOWN");
assert.equal(scoreDisplay("UNKNOWN"), "UNKNOWN");
assert.equal(scoreDisplay(""), "UNKNOWN");
assert.equal(scoreDisplay(0), "0");
assert.equal(scoreDisplay(70), "70");

assert.equal(marketDataState({ data_quality: { state: "STALE" } }), "STALE");
assert.equal(marketDataState({ data_state: "LIVE" }), "LIVE");
assert.equal(marketDataState({}), "UNKNOWN");

assert.equal(
  traderFacingErrorMessage({ code: "INVALID_CREDENTIALS", message: "gateway boom traceback" }),
  "Broker login or password was not accepted.",
);
assert.equal(
  traderFacingErrorMessage({
    code: "not_found",
    details: { reason: "not_connected" },
    message: "No active broker connection for this account",
  }),
  "Connect your broker account to start.",
);
assert.equal(
  traderFacingErrorMessage({
    message: "Weltrade connect failed: ConnectionRefusedError traceback password=secret",
  }),
  "Could not verify the broker connection.",
);

{
  const merged = mergeCatalogueRows(
    [{ broker_symbol: "EURUSD_i", asset_class: "FX", data_quality: { state: "LIVE" } }],
    [{ broker_symbol: "EURUSD_i", opportunity_score: 72, direction: "BUY" }],
  );
  assert.equal(merged.length, 1);
  assert.equal(merged[0]?.opportunity_score, 72);
  assert.equal(mergeCatalogueRows([], [{ symbol: "FAKE" }]).length, 0);
}

console.log("trader-ux.test.ts ok");
