/**
 * Phase 49 trader UX — connection labels, unavailable vs empty, error copy.
 * Run: node --experimental-strip-types src/lib/trading/trader-ux.test.ts
 */
import assert from "node:assert/strict";
import {
  catalogueViewState,
  EMPTY_MARKET_FILTERS,
  filterMarketRows,
  isLiveBrokerCatalogue,
  marketDataState,
  mergeCatalogueRows,
  numericDisplay,
  passwordClearedAfterSubmit,
  presentAssetClasses,
  priceDisplay,
  RESEARCH_NOT_AUTHORIZATION,
  resolveConnectionPresentation,
  robotDisplayState,
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

{
  const connected = {
    ux_state: "ROBOT_READY",
    broker: "Connected",
    connection: "Healthy",
    account: "16••06",
    server: "Wel***eal",
    catalogue_source: "LIVE_BROKER",
    catalogue_unavailable: false,
    robot: "Stopped",
  };
  const view = resolveConnectionPresentation(connected);
  assert.equal(view.state, "CONNECTED");
  assert.equal(view.connected, true);
}

{
  const view = resolveConnectionPresentation({
    ux_state: "NO_BROKER",
    broker: "Disconnected",
  });
  assert.equal(view.state, "BROKER_NOT_CONNECTED");
  assert.equal(view.connected, false);
}

{
  const unavailable = catalogueViewState({
    connected: true,
    mismatch: false,
    liveBrokerSession: false,
    catalogueUnavailable: true,
    snapshotFetched: true,
    snapshotError: false,
    catalogueSource: "UNAVAILABLE",
    instrumentCount: 0,
  });
  assert.equal(unavailable, "UNAVAILABLE");
}

{
  const live = catalogueViewState({
    connected: true,
    mismatch: false,
    liveBrokerSession: true,
    catalogueUnavailable: false,
    snapshotFetched: true,
    snapshotError: false,
    catalogueSource: "LIVE_BROKER",
    instrumentCount: 4,
  });
  assert.equal(live, "LIVE_ROWS");
}

{
  const empty = catalogueViewState({
    connected: true,
    mismatch: false,
    liveBrokerSession: true,
    catalogueUnavailable: false,
    snapshotFetched: true,
    snapshotError: false,
    catalogueSource: "LIVE_BROKER",
    instrumentCount: 0,
  });
  assert.equal(empty, "LIVE_EMPTY");
  assert.notEqual(empty, "UNAVAILABLE");
}

assert.equal(scoreDisplay(null), "UNKNOWN");
assert.equal(numericDisplay(null), "—");
assert.equal(numericDisplay(undefined), "—");
assert.equal(numericDisplay(""), "—");
assert.notEqual(numericDisplay(null), "0");
assert.equal(numericDisplay(0), "0");
assert.equal(priceDisplay(null), "—");
assert.equal(priceDisplay(1.23456), "1.23456");

assert.equal(
  presentAssetClasses([
    { asset_class: "FOREX" },
    { asset_class: "METALS" },
    { asset_class: "FOREX" },
  ]).join(","),
  "FOREX,METALS",
);
assert.equal(presentAssetClasses([{ asset_class: "UNKNOWN" }]).length, 0);

{
  const rows = [
    { broker_symbol: "EURUSD_i", description: "Euro vs US Dollar", asset_class: "FOREX", session: "LONDON", regime: "TREND", data_quality: { state: "LIVE" } },
    { broker_symbol: "XAUUSD_i", description: "Gold", asset_class: "METALS", session: "NEWYORK", data_quality: { state: "STALE" } },
  ];
  assert.equal(filterMarketRows(rows, { ...EMPTY_MARKET_FILTERS, q: "xau" }).length, 1);
  assert.equal(filterMarketRows(rows, { ...EMPTY_MARKET_FILTERS, assetClass: "FOREX" }).length, 1);
  assert.equal(filterMarketRows(rows, { ...EMPTY_MARKET_FILTERS, q: "eur" })[0]?.broker_symbol, "EURUSD_i");
}

assert.equal(
  robotDisplayState({ broker: "Disconnected", ux_state: "NO_BROKER" }),
  "BLOCKED",
);
assert.equal(
  robotDisplayState({
    broker: "Connected",
    ux_state: "ROBOT_RUNNING",
    robot: "Running",
    catalogue_unavailable: false,
    catalogue_source: "LIVE_BROKER",
  }),
  "RUNNING",
);

assert.equal(passwordClearedAfterSubmit("secret", true), "");
assert.equal(passwordClearedAfterSubmit("secret", false), "secret");
assert.equal(RESEARCH_NOT_AUTHORIZATION.includes("NOT A TRADE AUTHORIZATION"), true);

assert.equal(
  traderFacingErrorMessage({
    code: "ACCOUNT_SESSION_MISMATCH",
    message: "OMS blocked",
  }),
  "Your trading session needs to be reconnected.",
);

console.log("trader-ux.test.ts ok");
