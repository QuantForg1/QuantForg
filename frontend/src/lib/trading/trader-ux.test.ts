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
  sessionOwnership,
  traderFacingErrorMessage,
  defaultSortedSignals,
  EMPTY_SIGNAL_FILTERS,
  filterSignalRows,
  isHighConfidence,
  mergeResearchSignalFields,
  presentField,
  signalAvailability,
  signalBoardDirection,
  signalFeedState,
  signalFreshness,
  signalSummary,
  signalWhyFactors,
  sortSignalRows,
  strongestSetupLabel,
  unavailableSignalsTitle,
  accountHealth,
  accountHealthSummary,
  closedTradeStats,
  connectionShortLabel,
  EXPLANATION_UNAVAILABLE,
  exposureUnavailableReason,
  INSUFFICIENT_SAMPLE,
  lastUpdatedCopy,
  moneyDisplay,
  portfolioAccount,
  positionExposureLabel,
  positionSideLabel,
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
    ownership: "owned",
    owned: true,
  });
  assert.equal(view.state, "CONNECTED");
  assert.equal(view.label, "CONNECTED");
  assert.equal(view.liveBrokerCatalogue, true);
  assert.equal(view.maskedLogin, "16••06");
  assert.equal(view.ownership, "owned");
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
assert.equal(sessionOwnership({ ownership: "owned" }), "owned");
assert.equal(sessionOwnership({ owned: true }), "owned");
assert.equal(sessionOwnership({}), "none");

assert.equal(
  traderFacingErrorMessage({
    code: "ACCOUNT_SESSION_MISMATCH",
    message: "OMS blocked",
  }),
  "Your trading session needs to be reconnected.",
);

{
  assert.equal(signalBoardDirection({ direction: "WAIT" }), "WATCH");
  assert.equal(signalBoardDirection({ direction: "BUY" }), "BUY");
  assert.equal(presentField(null), "Not available");
  assert.equal(presentField("UNKNOWN"), "Not available");
  assert.equal(presentField("TREND"), "TREND");
}

{
  const live = signalAvailability("LIVE_EMPTY");
  assert.equal(live, "LIVE_EMPTY");
  const summaryEmpty = signalSummary({
    availability: "LIVE_EMPTY",
    rows: [],
    instrumentCount: 0,
    lastUpdate: "2026-08-29T00:00:00Z",
  });
  assert.equal(summaryEmpty.active, "0");
  assert.equal(summaryEmpty.markets, "0");
}

{
  const unavailable = signalSummary({
    availability: "UNAVAILABLE",
    rows: [],
    instrumentCount: 0,
    lastUpdate: null,
  });
  assert.equal(unavailable.active, "—");
  assert.equal(unavailable.buy, "—");
  assert.notEqual(unavailable.active, "0");
  const copy = unavailableSignalsTitle({ noBroker: true });
  assert.equal(copy.title, "SIGNALS UNAVAILABLE");
}

{
  const rows = [
    { symbol: "EURUSD", direction: "BUY", asset_class: "FOREX", opportunity_score: 80, qualified_research: true, research_rank_score: 12 },
    { symbol: "GBPUSD", direction: "WAIT", asset_class: "FOREX", opportunity_score: 40, research_rank_score: 4 },
    { symbol: "XAUUSD_i", direction: "SELL", asset_class: "METALS", opportunity_score: 90, board_status: "QUALIFIED", research_rank_score: 20 },
  ];
  assert.equal(filterSignalRows(rows, { ...EMPTY_SIGNAL_FILTERS, direction: "BUY" }).length, 1);
  assert.equal(filterSignalRows(rows, { ...EMPTY_SIGNAL_FILTERS, direction: "WATCH" }).length, 1);
  assert.equal(isHighConfidence(rows[0]!), true);
  const ranked = defaultSortedSignals(rows);
  assert.equal(ranked[0]?.symbol, "XAUUSD_i");
  assert.equal(sortSignalRows(rows, "strongest")[0]?.symbol, "XAUUSD_i");
  assert.equal(strongestSetupLabel(rows, "LIVE_ROWS"), "XAUUSD_i SELL");
  assert.equal(strongestSetupLabel(rows, "UNAVAILABLE"), "—");
  const buySell = signalSummary({
    availability: "LIVE_ROWS",
    rows,
    instrumentCount: 3,
    lastUpdate: "2026-08-30T00:00:00Z",
  });
  assert.equal(buySell.buy, "1");
  assert.equal(buySell.sell, "1");
  assert.equal(buySell.strongest, "XAUUSD_i SELL");
}

{
  assert.equal(
    signalFeedState({
      loading: false,
      noBroker: true,
      mismatch: false,
      snapshotError: false,
      availability: "UNAVAILABLE",
      rows: [],
    }),
    "DISCONNECTED",
  );
  assert.equal(
    signalFeedState({
      loading: false,
      noBroker: false,
      mismatch: false,
      snapshotError: false,
      availability: "UNAVAILABLE",
      rows: [],
    }),
    "CATALOGUE_UNAVAILABLE",
  );
}

{
  const merged = mergeResearchSignalFields(
    [{ symbol: "EURUSD", direction: "BUY" }],
    [{ symbol: "EURUSD", entry_candidate: "1.0800", SL_candidate: "1.0700" }],
  );
  assert.equal(merged[0]?.entry_candidate, "1.0800");
  assert.equal(presentField(merged[0]?.entry_candidate), "1.0800");
}

{
  assert.equal(moneyDisplay(null, false), "—");
  assert.equal(moneyDisplay(0, true), "0");
  assert.notEqual(moneyDisplay(null, false), "0");
  assert.equal(positionSideLabel("buy"), "BUY");
  assert.equal(positionSideLabel("short"), "SELL");
  assert.equal(portfolioAccount({ account: { balance: "10" } }).balance, "10");
  assert.equal(exposureUnavailableReason(), "EXPOSURE DATA UNAVAILABLE");
  const emptyStats = closedTradeStats([], true);
  assert.equal(emptyStats.status, "INSUFFICIENT_SAMPLE");
  assert.equal(emptyStats.winRate, INSUFFICIENT_SAMPLE);
  assert.notEqual(emptyStats.realized, "0");
  const unavailableStats = closedTradeStats([{ profit: "12" }], false);
  assert.equal(unavailableStats.realized, "—");
  assert.notEqual(unavailableStats.realized, "0");
  const readyStats = closedTradeStats(
    [
      { profit: "10" },
      { profit: "4" },
      { profit: "-2" },
      { profit: "1" },
      { profit: "-1" },
    ],
    true,
  );
  assert.equal(readyStats.status, "READY");
  assert.equal(readyStats.sample, "5");
  assert.equal(readyStats.drawdown, INSUFFICIENT_SAMPLE);
}

{
  const health = accountHealth({
    connection: {
      state: "BROKER_NOT_CONNECTED",
      label: "BROKER NOT CONNECTED",
      tone: "danger",
      health: "Disconnected",
      maskedLogin: "—",
      server: "—",
      lastVerified: null,
      connected: false,
      ownership: "none",
      catalogueUnavailable: true,
      accountUnavailable: true,
      liveBrokerCatalogue: false,
    },
    robot: "BLOCKED",
    liveCatalogue: false,
    positionsError: false,
    positionsLoaded: false,
    marginAvailable: false,
    accountUnavailable: true,
  });
  assert.equal(health.find((h) => h.id === "broker")?.state, "Blocked");
  assert.equal(health.find((h) => h.id === "robot")?.state, "Blocked");
  assert.equal(accountHealthSummary(health), "Unavailable");
}

{
  assert.equal(signalFreshness({ data_quality: { state: "LIVE" } }), "LIVE");
  assert.equal(signalFreshness({ data_quality: { state: "STALE" } }), "STALE");
  assert.equal(signalFreshness({ data_state: "ERROR" }), "UNAVAILABLE");
  assert.equal(signalFreshness({}), "UNAVAILABLE");
  const recent = new Date(Date.now() - 60_000).toISOString();
  assert.equal(signalFreshness({ timestamp: recent }), "RECENT");
  assert.equal(lastUpdatedCopy(null), "");
  assert.equal(lastUpdatedCopy(""), "");
  assert.match(lastUpdatedCopy(new Date(Date.now() - 12_000).toISOString()), /Last updated 1[0-4] seconds ago/);
  assert.equal(positionExposureLabel("buy"), "LONG");
  assert.equal(positionExposureLabel("short"), "SHORT");
  assert.equal(connectionShortLabel("BROKER_NOT_CONNECTED"), "DISCONNECTED");
  assert.equal(connectionShortLabel("ACCOUNT_SESSION_MISMATCH"), "SESSION MISMATCH");
  assert.equal(connectionShortLabel("CONNECTED"), "CONNECTED");
  assert.equal(signalWhyFactors({}).length, 0);
  assert.equal(EXPLANATION_UNAVAILABLE, "EXPLANATION UNAVAILABLE");
}

{
  const buy = filterSignalRows(
    [
      { symbol: "EURUSD", direction: "BUY", asset_class: "FOREX" },
      { symbol: "GBPUSD", direction: "SELL", asset_class: "FOREX" },
    ],
    { ...EMPTY_SIGNAL_FILTERS, direction: "SELL" },
  );
  assert.equal(buy.length, 1);
  assert.equal(buy[0]?.symbol, "GBPUSD");
}

console.log("trader-ux.test.ts ok");
