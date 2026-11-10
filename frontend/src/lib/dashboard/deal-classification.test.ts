/**
 * Deal classification contracts for operational truth.
 * Run: node --experimental-strip-types src/lib/dashboard/deal-classification.test.ts
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  classifyDealKind,
  isTradeDeal,
  latestTradeDeal,
  resolveLastExecutionView,
} from "./deal-classification.ts";
import { netDealPnl } from "./performance-math.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const pageSrc = readFileSync(join(root, "app/(app)/dashboard/page.tsx"), "utf8");
const robotSrc = readFileSync(
  join(root, "components/trading/dashboard-intelligence/robot-activity-panel.tsx"),
  "utf8",
);
const activitySrc = readFileSync(
  join(root, "components/trading/dashboard-intelligence/recent-activity-panel.tsx"),
  "utf8",
);
const traderUx = readFileSync(join(root, "lib/trading/trader-ux.ts"), "utf8");
const perfSrc = readFileSync(join(root, "lib/dashboard/performance-window.ts"), "utf8");
const statsSrc = readFileSync(join(root, "lib/dashboard/deal-stats.ts"), "utf8");

assert.match(pageSrc, /resolveLastExecutionView/);
assert.match(pageSrc, /live_submit_enabled/);
assert.match(robotSrc, /Weltrade LIVE/);
assert.match(robotSrc, /Multi-account LIVE/);
assert.match(robotSrc, /stale/);
assert.match(activitySrc, /activityKindFromDeal|classifyDealKind|deposit/);
assert.match(traderUx, /Weltrade single-account/);
assert.match(perfSrc, /isTradeDeal/);
assert.match(statsSrc, /isTradeDeal/);

const deposit = {
  comment: "Deposit from #12439799",
  profit: 50,
  time: "2026-11-02T12:00:00.000Z",
  type: "balance",
};
const withdrawal = {
  comment: "Withdrawal to bank",
  profit: -20,
  time: "2026-11-03T12:00:00.000Z",
  deal_type: "balance",
};
const balanceAdj = {
  comment: "Balance adjustment",
  profit: 5,
  time: "2026-11-04T12:00:00.000Z",
  type: "correction",
};
const win = {
  symbol: "XAUUSD",
  side: "buy",
  deal_type: "deal",
  profit: 12,
  commission: -0.5,
  swap: 0,
  time: "2026-11-05T10:00:00.000Z",
  status: "filled",
};
const loss = {
  symbol: "XAUUSD",
  side: "sell",
  type: "sell",
  profit: -8,
  commission: -0.5,
  swap: -0.2,
  time: "2026-11-05T11:00:00.000Z",
};

assert.equal(classifyDealKind(deposit), "deposit");
assert.equal(classifyDealKind(withdrawal), "withdrawal");
assert.equal(classifyDealKind(balanceAdj), "balance");
assert.equal(classifyDealKind(win), "trade");
assert.equal(isTradeDeal(deposit), false);
assert.equal(isTradeDeal(withdrawal), false);
assert.equal(isTradeDeal(balanceAdj), false);
assert.equal(isTradeDeal(win), true);

// Deposit must not become last execution via deal fallback.
{
  const view = resolveLastExecutionView({
    deals: [deposit, win],
    now: Date.parse("2026-11-05T12:00:00.000Z"),
  });
  assert.equal(view.source, "trade_deal");
  assert.match(view.resultLabel, /XAUUSD|filled/i);
  assert.doesNotMatch(view.resultLabel, /Deposit/i);
}

// Deposit-only history must not invent an execution result.
{
  const view = resolveLastExecutionView({
    deals: [deposit],
    now: Date.parse("2026-11-05T12:00:00.000Z"),
  });
  assert.equal(view.source, "none");
  assert.doesNotMatch(view.resultLabel, /Deposit/i);
}

// OMS fields win over deal history.
{
  const view = resolveLastExecutionView({
    sessionExecutionAt: "2026-11-05T09:00:00.000Z",
    sessionExecutionResult: "OMS fill ticket 99",
    deals: [deposit],
    now: Date.parse("2026-11-05T12:00:00.000Z"),
  });
  assert.equal(view.source, "oms");
  assert.equal(view.resultLabel, "OMS fill ticket 99");
  assert.equal(view.stale, false);
}

// Stale OMS timestamp flagged.
{
  const view = resolveLastExecutionView({
    robotExecutionAt: "2026-11-02T12:00:00.000Z",
    robotExecutionResult: "filled",
    deals: [],
    now: Date.parse("2026-11-10T12:00:00.000Z"),
  });
  assert.equal(view.stale, true);
}

// Newest by timestamp wins (loss at 11:00 after win at 10:00).
assert.equal(latestTradeDeal([deposit, loss, win])?.profit, -8);
assert.equal(latestTradeDeal([deposit, win])?.profit, 12);

// Closed-trade stats ignore deposits/withdrawals/balance adjustments.
{
  const rows = [deposit, withdrawal, balanceAdj, win, loss];
  const trades = rows.filter(isTradeDeal);
  assert.equal(trades.length, 2);
  const realized = trades.reduce((sum, d) => sum + netDealPnl(d), 0);
  assert.equal(Number(realized.toFixed(2)), 2.8);
  const wins = trades.filter((d) => netDealPnl(d) > 0);
  assert.equal(wins.length / trades.length, 0.5);
}

console.log("deal classification contract ok");
