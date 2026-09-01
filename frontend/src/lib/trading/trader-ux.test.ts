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
  RESEARCH_OPPORTUNITY,
  RESEARCH_SIGNAL,
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
  signalFeedStateLabel,
  signalFreshness,
  signalFreshnessLabel,
  signalSummary,
  signalWhyFactors,
  signalWhyPreview,
  sortSignalRows,
  strongestSetupLabel,
  unavailableSignalsTitle,
  accountHealth,
  accountHealthSummary,
  closedTradeStats,
  connectionShortLabel,
  dataSourceLabel,
  EXPLANATION_UNAVAILABLE,
  exposureUnavailableReason,
  INSUFFICIENT_SAMPLE,
  isValidBrokerSymbol,
  lastUpdatedCopy,
  moneyDisplay,
  cataloguePageSlice,
  catalogueStatusLabel,
  hasResearchSignal,
  knownInstrumentCountLabel,
  marketDirectionLabel,
  marketSignalLabel,
  normalizeSignalCenterPayload,
  researchDeskLiveTradingStatus,
  researchFeedState,
  researchFeedStateLabel,
  researchLifecycleCounts,
  researchMetricDisplay,
  researchCoverageLabel,
  researchProgressCopy,
  researchSignalsEmptyCopy,
  researchUniverseViewState,
  resolveAnalysisDeskStatus,
  analysisDeskStatusLabel,
  knownUniverseCountLabel,
  accountConnectionHint,
  skippedMalformedInstrumentCount,
  portfolioAccount,
  positionExposureLabel,
  positionSideLabel,
  strongestEdgeLabel,
  topResearchOpportunities,
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
  assert.equal(merged[0]?.has_research_signal, true);
  assert.equal(mergeCatalogueRows([], [{ symbol: "FAKE" }]).length, 0);
  const noSignal = mergeCatalogueRows(
    [{ broker_symbol: "USDJPY", asset_class: "FOREX" }],
    [],
  );
  assert.equal(noSignal[0]?.has_research_signal, false);
  assert.equal(marketSignalLabel(noSignal[0] ?? {}), "NO SIGNAL");
  assert.equal(marketDirectionLabel(noSignal[0] ?? {}), "—");
  assert.equal(researchMetricDisplay(noSignal[0] ?? {}, 70), "—");
  assert.equal(marketSignalLabel(merged[0] ?? {}), "BUY");
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
assert.equal(presentAssetClasses([{ asset_class: "UNKNOWN" }]).join(","), "UNKNOWN");

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
  assert.equal(signalBoardDirection({ direction: "WAIT" }), "NEUTRAL");
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
  assert.equal(summaryEmpty.strongestEdge, "—");
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
  assert.equal(unavailable.strongestEdge, "—");
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
  assert.equal(filterSignalRows(rows, { ...EMPTY_SIGNAL_FILTERS, direction: "NEUTRAL" }).length, 1);
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
  assert.equal(buySell.neutral, "1");
  assert.equal(buySell.strongest, "XAUUSD_i SELL");
}

{
  assert.equal(researchCoverageLabel({ coverage_pct: 37.5 }), "37.5%");
  assert.equal(
    researchCoverageLabel({ instruments_discovered: 100, instruments_analyzed: 25 }),
    "25%",
  );
  assert.equal(
    researchCoverageLabel({
      instruments_eligible: 40,
      instruments_analyzed: 40,
      instruments_discovered: 83,
    }),
    "100%",
  );
  assert.equal(researchCoverageLabel({}), "—");
  assert.equal(
    researchProgressCopy({ instruments_discovered: 1000, instruments_analyzed: 250 }),
    "Analyzing 250 / 1,000 instruments",
  );
  assert.equal(
    researchProgressCopy({
      instruments_eligible: 40,
      instruments_analyzed: 40,
      instruments_discovered: 83,
    }),
    "Analyzing 40 / 40 eligible",
  );
  assert.equal(
    signalWhyPreview({
      reason: "Bullish structure with positive momentum",
      evidence: { WHY_THIS_DIRECTION: "BUY bias" },
    }),
    "Bullish structure with positive momentum",
  );
  assert.equal(signalWhyPreview({}), "EXPLANATION UNAVAILABLE");
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
  assert.equal(moneyDisplay(null, false), "Unavailable");
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
  assert.equal(signalFreshnessLabel("LIVE"), "LIVE DATA");
  assert.equal(signalFreshnessLabel("UNAVAILABLE"), "DATA UNAVAILABLE");
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
  assert.equal(connectionShortLabel("BROKER_NOT_CONNECTED"), "BROKER NOT CONNECTED");
  assert.equal(connectionShortLabel("ACCOUNT_SESSION_MISMATCH"), "SESSION MISMATCH");
  assert.equal(connectionShortLabel("CONNECTED"), "CONNECTED");
  assert.equal(connectionShortLabel("DISCONNECTED"), "DISCONNECTED");
  assert.equal(connectionShortLabel("DATA_UNAVAILABLE"), "UNAVAILABLE");
  assert.equal(signalFeedStateLabel("LIVE"), "LIVE");
  assert.equal(
    dataSourceLabel({ liveBroker: true, catalogueSource: "LIVE_BROKER" }),
    "LIVE_BROKER",
  );
  assert.equal(
    dataSourceLabel({ liveBroker: false, catalogueSource: "LIVE_BROKER" }),
    "UNAVAILABLE",
  );
  assert.equal(RESEARCH_SIGNAL, "RESEARCH SIGNAL");
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
  const searched = filterSignalRows(
    [
      { symbol: "EURUSD", direction: "BUY" },
      { symbol: "GBPUSD", direction: "SELL" },
    ],
    { ...EMPTY_SIGNAL_FILTERS, q: "gbp" },
  );
  assert.equal(searched.length, 1);
  assert.equal(searched[0]?.symbol, "GBPUSD");
}

{
  const ranked = [
    { symbol: "AAA", direction: "BUY", research_rank_score: 1, directional_edge: 3 },
    { symbol: "BBB", direction: "SELL", research_rank_score: 9, directional_edge: 8 },
  ];
  assert.equal(strongestEdgeLabel(ranked, "LIVE_ROWS"), "8");
  assert.equal(strongestEdgeLabel(ranked, "UNAVAILABLE"), "—");
  assert.notEqual(strongestEdgeLabel([{ symbol: "AAA", direction: "BUY" }], "LIVE_ROWS"), "0");
}

{
  assert.equal(isValidBrokerSymbol("EURUSD_i"), true);
  assert.equal(isValidBrokerSymbol("XAUUSD_i"), true);
  assert.equal(isValidBrokerSymbol(""), false);
  assert.equal(isValidBrokerSymbol("???"), false);
  assert.equal(isValidBrokerSymbol("UNKNOWN"), false);
  const kept = mergeCatalogueRows(
    [
      { broker_symbol: "EURUSD_i", asset_class: "FOREX" },
      { broker_symbol: "", asset_class: "FOREX" },
      { broker_symbol: "???", asset_class: "FOREX" },
    ],
    [],
  );
  assert.equal(kept.length, 1);
  assert.equal(kept[0]?.broker_symbol, "EURUSD_i");
  const directed = filterMarketRows(
    [
      { broker_symbol: "EURUSD", direction: "BUY", asset_class: "FOREX", has_research_signal: true },
      { broker_symbol: "GBPUSD", direction: "SELL", asset_class: "FOREX", has_research_signal: true },
      { broker_symbol: "USDJPY", direction: "BUY", asset_class: "FOREX", has_research_signal: false },
    ],
    { ...EMPTY_MARKET_FILTERS, direction: "BUY" },
  );
  assert.equal(directed.length, 1);
  assert.equal(directed[0]?.broker_symbol, "EURUSD");
  const tops = topResearchOpportunities(
    [
      { symbol: "AAA", direction: "BUY", research_rank_score: 1 },
      { symbol: "BBB", direction: "SELL", research_rank_score: 9 },
      { symbol: "CCC", direction: "WAIT", research_rank_score: 99 },
    ],
    "LIVE_ROWS",
    2,
  );
  assert.equal(tops[0]?.symbol, "BBB");
  assert.equal(tops.length, 2);
  assert.equal(topResearchOpportunities([], "UNAVAILABLE", 4).length, 0);
  assert.equal(RESEARCH_OPPORTUNITY.includes("RESEARCH"), true);
}

{
  const universe = Array.from({ length: 120 }, (_, i) => ({
    broker_symbol: `SYM${String(i).padStart(3, "0")}`,
  }));
  assert.equal(universe.length, 120);
  assert.equal(cataloguePageSlice(universe, 1).length, 50);
  assert.equal(cataloguePageSlice(universe, 3).length, 20);
  assert.equal(cataloguePageSlice(universe, 1)[0]?.broker_symbol, "SYM000");
  assert.equal(skippedMalformedInstrumentCount([
    { broker_symbol: "EURUSD" },
    { broker_symbol: "" },
    { broker_symbol: "???" },
  ]), 2);
  assert.equal(hasResearchSignal({ has_research_signal: false, direction: "SELL" }), false);
  assert.equal(
    hasResearchSignal({
      direction: "NONE",
      board_status: "DISCOVERED",
      opportunity_score: 0,
    }),
    false,
  );
  assert.equal(
    hasResearchSignal({
      direction: "BUY",
      board_status: "ANALYZED",
      opportunity_score: 73,
      research_rank_score: 10,
    }),
    true,
  );
  assert.equal(marketSignalLabel({ has_research_signal: false, direction: "SELL" }), "NO SIGNAL");
  assert.equal(catalogueStatusLabel("UNAVAILABLE"), "CATALOGUE_UNAVAILABLE");
  assert.equal(catalogueStatusLabel("LIVE_EMPTY"), "EMPTY");
  assert.equal(catalogueStatusLabel("LIVE_ROWS"), "LIVE_BROKER");
  assert.equal(knownInstrumentCountLabel("UNAVAILABLE", 0), "");
  assert.equal(knownInstrumentCountLabel("LIVE_EMPTY", 0), "0");
  assert.equal(knownInstrumentCountLabel("LIVE_ROWS", 500), "500");
  assert.equal(
    sortSignalRows(
      [
        { broker_symbol: "AAA", has_research_signal: false },
        { broker_symbol: "BBB", has_research_signal: true, direction: "BUY" },
      ],
      "signal",
    )[0]?.broker_symbol,
    "BBB",
  );
}

{
  const empty = normalizeSignalCenterPayload(null);
  assert.equal(empty.availability, "NOT_READY");
  assert.equal(empty.rows.length, 0);
  assert.equal(empty.universeSize, null);
  const fabricated = normalizeSignalCenterPayload({
    fabricated: true,
    test_synthetic: true,
    items: [{ symbol: "EURUSD", direction: "BUY", opportunity_score: 80 }],
  });
  assert.equal(fabricated.fabricatedBlocked, true);
  assert.equal(fabricated.rows.length, 0);
  assert.equal(fabricated.availability, "LIVE_EMPTY");
  const live = normalizeSignalCenterPayload({
    as_of: "2026-08-30T00:00:00Z",
    source: "live_multi_asset_scan",
    universe_size: 2000,
    items: [
      { symbol: "XAUUSD_i", direction: "BUY", opportunity_score: 70, directional_edge: 5, rr: "1.20", asset_class: "metals", session: "LONDON", time_generated: "2026-08-30T00:00:00Z" },
      { symbol: "EURUSD", direction: "NONE", opportunity_score: 10 },
      { symbol: "BAD???", direction: "BUY", opportunity_score: 90 },
    ],
  });
  assert.equal(live.availability, "LIVE_ROWS");
  assert.equal(live.rows.length, 1);
  assert.equal(live.rows[0]?.broker_symbol, "XAUUSD_I");
  assert.equal(live.rows[0]?.has_research_signal, true);
  assert.equal(live.rows[0]?.asset_class, "METALS");
  assert.equal(live.universeSize, 2000);
  assert.equal(knownUniverseCountLabel(null, true), "—");
  assert.equal(knownUniverseCountLabel(2000, true), "2000");
  assert.equal(accountConnectionHint(resolveConnectionPresentation({ ux_state: "NO_BROKER" })).detail, "NOT CONNECTED");
  assert.equal(
    researchFeedStateLabel(
      researchFeedState({
        loading: false,
        fetchError: true,
        availability: "UNAVAILABLE",
        rows: [],
      }),
    ),
    "INTELLIGENCE DATA UNAVAILABLE",
  );
  assert.equal(
    researchSignalsEmptyCopy({ empty: true, universeSize: 2000 }).title,
    "NO ACTIVE SIGNALS",
  );
  assert.equal(
    resolveAnalysisDeskStatus({
      loading: false,
      fetchError: false,
      availability: "LIVE_EMPTY",
      rows: [],
      asOf: "2026-08-30T12:00:00Z",
      universeSize: 2000,
      nowMs: Date.parse("2026-08-30T12:05:00Z"),
    }),
    "NO_ACTIVE_SIGNALS",
  );
  assert.equal(
    analysisDeskStatusLabel("SCANNER_UNAVAILABLE"),
    "SCANNER UNAVAILABLE",
  );
  assert.equal(
    resolveAnalysisDeskStatus({
      loading: false,
      fetchError: true,
      availability: "UNAVAILABLE",
      rows: [],
    }),
    "SCANNER_UNAVAILABLE",
  );
}

{
  // Phase 73 — do not invent research signals from bare WAIT / OMS abort codes.
  const bareWait = normalizeSignalCenterPayload({
    as_of: "2026-08-30T00:00:00Z",
    items: [
      { symbol: "EURUSD", direction: "WAIT", status: "MAX_POSITIONS_REACHED" },
      {
        symbol: "GBPUSD",
        direction: "WAIT",
        opportunity_score: 55,
        research_rank_score: 4,
        board_status: "ANALYZED",
      },
      {
        symbol: "USDJPY",
        direction: "BUY",
        opportunity_score: 80,
        qualified_research: true,
        board_status: "QUALIFIED",
      },
    ],
  });
  assert.equal(bareWait.rows.length, 2);
  assert.equal(
    bareWait.rows.some((r) => String(r.symbol) === "EURUSD"),
    false,
  );
  const gbp = bareWait.rows.find((r) => String(r.symbol) === "GBPUSD");
  assert.equal(gbp?.board_status, "ANALYZED");
  assert.notEqual(gbp?.board_status, "MAX_POSITIONS_REACHED");
  const jpy = bareWait.rows.find((r) => String(r.symbol) === "USDJPY");
  assert.equal(jpy?.qualified_research, true);
  assert.equal(isHighConfidence(jpy!), true);
  assert.equal(
    normalizeSignalCenterPayload({
      items: [
        {
          symbol: "EURUSD",
          direction: "BUY",
          opportunity_score: 70,
          status: "NO_TRADE",
        },
      ],
    }).rows[0]?.board_status,
    undefined,
  );
}

{
  // Global research catalogue is independent of the viewer's MT5 session.
  const disconnected = researchUniverseViewState({
    snapshotFetched: true,
    snapshotError: false,
    catalogueSource: "LIVE_BROKER",
    instrumentCount: 12,
  });
  assert.equal(disconnected, "LIVE_ROWS");
  assert.equal(
    catalogueViewState({
      connected: false,
      mismatch: false,
      liveBrokerSession: false,
      catalogueUnavailable: true,
      snapshotFetched: true,
      snapshotError: false,
      catalogueSource: "LIVE_BROKER",
      instrumentCount: 12,
    }),
    "UNAVAILABLE",
  );
  const liveHint = researchDeskLiveTradingStatus({
    connected: false,
    state: "BROKER_NOT_CONNECTED",
  });
  assert.equal(liveHint.state, "LIVE_TRADING_UNAVAILABLE");
  assert.equal(liveHint.detail, "Unavailable until broker connection");
  const connectedHint = researchDeskLiveTradingStatus({
    connected: true,
    state: "CONNECTED",
  });
  assert.equal(connectedHint.state, "LIVE_TRADING_DISABLED");
}

{
  const counts = researchLifecycleCounts([
    { research_lifecycle: "ANALYZED" },
    { research_lifecycle: "QUEUED" },
    { research_lifecycle: "MARKET_CLOSED" },
    { research_lifecycle: "FAILED" },
    { research_lifecycle: "UNSUPPORTED" },
    { research_lifecycle: "DATA_UNAVAILABLE" },
    { research_lifecycle: "READY" },
  ]);
  assert.equal(counts.analyzed, 1);
  assert.equal(counts.queued, 1);
  assert.equal(counts.closed, 1);
  assert.equal(counts.failed, 1);
  assert.equal(counts.unsupported, 1);
  assert.equal(counts.unavailable, 1);
  assert.equal(counts.ready, 1);
}

{
  const why = signalWhyFactors({
    direction: "BUY",
    reason: "Trend aligned with momentum",
    evidence: {
      WHY_THIS_DIRECTION: "Higher highs on H1",
      MOMENTUM: "Positive",
      STRUCTURE_EVIDENCE: "Break of structure",
      RISK_CONDITIONS: "Defined invalidation",
    },
    entry: 1.085,
    stop_loss: 1.08,
    take_profit: 1.095,
    price: 1.0845,
  });
  assert.equal(why[0]?.label, "Direction");
  assert.equal(why[0]?.value, "BUY");
  assert.equal(
    why.some((f) => f.label === "Why the model prefers this direction"),
    true,
  );
  assert.equal(
    why.some((f) => /invent|always buy/i.test(f.value)),
    false,
  );
  const preview = signalWhyPreview({
    direction: "SELL",
    evidence: { WHY_THIS_DIRECTION: "Failed breakout" },
  });
  assert.notEqual(preview, EXPLANATION_UNAVAILABLE);
  assert.match(preview, /Failed breakout|SELL/);
}

console.log("trader-ux.test.ts ok");
