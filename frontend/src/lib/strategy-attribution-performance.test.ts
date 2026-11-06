/**
 * Strategy performance dashboard view-model — no invented metrics.
 * Run: node --experimental-strip-types src/lib/strategy-attribution-performance.test.ts
 */
import assert from "node:assert/strict";
import {
  buildStrategyPerformanceDashboardModel,
  classificationTone,
  formatMoney,
  formatPct,
  formatPf,
  scorecardChartRows,
} from "./strategy-attribution-performance.ts";

const sample = {
  as_of: "2026-11-06T12:00:00+00:00",
  broker_login: 12479147,
  reporting_period: "post_pr182",
  instrument: "XAUUSD",
  account_12260878_note: "Never merge without label.",
  advisory_only: true,
  mutates_engines: false,
  post_pr182: {
    label: "post_pr182",
    broker_login: 12479147,
    n: 2,
    attributed: 1,
    unattributed: 1,
    attribution_coverage_pct: 50,
    incomplete_cost_records: 1,
    realized_net_pnl: -1,
    net_profit: -1,
    win_rate: 0.5,
    profit_factor: 0.67,
    expectancy: -0.5,
    avg_win: 2,
    avg_loss: -3,
    max_drawdown: -3,
    max_consecutive_losses: 1,
    classification: "Insufficient attribution",
    buy: {
      n: 1,
      net: 2,
      win_rate: 1,
      profit_factor: null,
      expectancy: 2,
      avg_win: 2,
      avg_loss: 0,
      classification: "Promising but insufficient sample",
    },
    sell: {
      n: 1,
      net: -3,
      win_rate: 0,
      profit_factor: 0,
      expectancy: -3,
      avg_win: 0,
      avg_loss: -3,
      classification: "Negative expectancy (small sample — provisional)",
    },
    reversal_like_closes: 0,
    data_quality: { note: "costs_complete=False means absent" },
  },
  periods: {
    post_pr182: {
      label: "post_pr182",
      n: 2,
      attributed: 1,
      unattributed: 1,
      buy: { n: 1, net: 2 },
      sell: { n: 1, net: -3 },
      classification: "Insufficient attribution",
    },
    pre_pr180: {
      label: "pre_pr180",
      n: 0,
      attributed: 0,
      unattributed: 0,
      buy: { n: 0, net: 0 },
      sell: { n: 0, net: 0 },
      classification: "Insufficient data",
    },
  },
  five_pack_scorecards_post_pr182: [
    {
      strategy_id: "trend_continuation",
      strategy_name: "Trend Continuation Scalping",
      closed_trades: 1,
      net_pnl: 2,
      win_rate: 1,
      profit_factor: null,
      expectancy: 2,
      sample_size: 1,
      attribution_confidence: "bound_five_pack",
      classification: "Promising but insufficient sample",
      buy_n: 1,
      sell_n: 0,
      buy_net: 2,
      sell_net: 0,
    },
    {
      strategy_id: "smc_scalping",
      strategy_name: "SMC Scalping",
      closed_trades: 0,
      net_pnl: 0,
      sample_size: 0,
      attribution_confidence: "insufficient_data",
      classification: "Insufficient data",
      buy_n: 0,
      sell_n: 0,
    },
    {
      strategy_id: null,
      strategy_name: "Unattributed / unknown",
      closed_trades: 1,
      net_pnl: -3,
      sample_size: 1,
      attribution_confidence: "unknown",
      classification: "Insufficient attribution",
    },
  ],
  capital_protection: {
    buy_cascade: {
      active_anchors: 0,
      store_trusted: true,
      note: "Active durable BUY anchors only.",
    },
    sell_cascade: {
      active_anchors: 1,
      store_trusted: true,
      note: "Active durable SELL anchors only.",
    },
    reversal: { broker_confirmed_reversal_like_closes: 0 },
  },
  m1: {
    m1_micro_enabled: true,
    m1_live_submit: false,
    m1_live_oms_submission: "OFF",
    status: "DISABLED",
    recommendation: "LIVE submit off",
    display_rule: "M1 signal counts are not completed trades.",
  },
};

const model = buildStrategyPerformanceDashboardModel(sample);

assert.equal(model.brokerLogin, 12479147);
assert.equal(model.overview.n, 2);
assert.equal(model.overview.attributionCoveragePct, 50);
assert.equal(model.overview.unrealizedPnl, null);
assert.equal(model.overview.incompleteCostRecords, 1);
assert.equal(model.scorecards.length, 2);
assert.ok(model.unattributed);
assert.equal(model.unattributed?.strategyId, null);
assert.equal(model.unattributed?.isUnattributed, true);
assert.equal(model.m1.liveSubmitLabel, "OFF");
assert.equal(model.m1.liveSubmit, false);
assert.equal(model.capitalProtection.sellActiveAnchors, 1);
assert.equal(model.capitalProtection.historicalBlocksUnavailable, true);
assert.equal(model.mutatesEngines, false);
assert.equal(model.advisoryOnly, true);

const emptyCard = model.scorecards.find((c) => c.strategyId === "smc_scalping");
assert.ok(emptyCard?.isInsufficientData);

assert.equal(formatMoney(2), "+2.00");
assert.equal(formatMoney(-3), "-3.00");
assert.equal(formatMoney(null), "—");
assert.equal(formatPct(0.5), "50.0%");
assert.equal(formatPf(null), "—");
assert.equal(classificationTone("Positive expectancy demonstrated"), "ok");
assert.equal(classificationTone("Negative expectancy observed"), "bad");
assert.equal(classificationTone("Insufficient data"), "warn");

const chart = scorecardChartRows(model.scorecards);
assert.equal(chart.length, 2);
assert.equal(
  chart.find((r) => r.label === "smc_scalping")?.value,
  0,
  "insufficient-data strategies chart as flat zero without claiming P&L",
);

// Missing payload fields must not invent profitability
const sparse = buildStrategyPerformanceDashboardModel({});
assert.equal(sparse.overview.n, 0);
assert.equal(sparse.overview.realizedNetPnl, null);
assert.equal(sparse.scorecards.length, 0);
assert.equal(sparse.m1.liveSubmitLabel, "OFF");

console.log("strategy-attribution-performance.test.ts ok");
