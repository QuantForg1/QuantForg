/**
 * Derive account risk intelligence from live session + open exposure.
 * Uses OWNER_RISK_POLICY_DISPLAY ceilings for explanation only — does not
 * re-implement or bypass the production risk engine.
 */

import { OWNER_RISK_POLICY_DISPLAY } from "@/lib/trading/owner-risk-policy-display";
import { num } from "@/lib/desk";

export type RiskHealthState = "Healthy" | "Warning" | "Restricted" | "Halted";

export type RiskIntelligenceSnapshot = {
  state: RiskHealthState;
  reason: string;
  currentDrawdownPct: number;
  dailyLossUsedPct: number;
  dailyLossRemainingPct: number;
  aggregateOpenRiskPct: number;
  openPositionCount: number;
  maxConcurrentPositions: number;
  floatingPnl: number;
  equity: number;
  available: boolean;
};

export function deriveRiskIntelligence(input: {
  equity?: unknown;
  balance?: unknown;
  floatingPnl?: unknown;
  todayPnl?: unknown;
  openPositionCount?: number;
  riskLocked?: unknown;
  emergencyStop?: unknown;
  liveAuthorization?: unknown;
  ordersMaySubmit?: unknown;
}): RiskIntelligenceSnapshot {
  const equity = num(input.equity);
  const balance = num(input.balance);
  const floating = num(input.floatingPnl);
  const today = num(input.todayPnl);
  const openCount = Math.max(0, Math.floor(input.openPositionCount ?? 0));
  const policy = OWNER_RISK_POLICY_DISPLAY;

  const available = Number.isFinite(equity) && equity > 0;
  if (!available) {
    return {
      state: "Restricted",
      reason: "Broker session equity is unavailable. Risk meters cannot be computed.",
      currentDrawdownPct: NaN,
      dailyLossUsedPct: NaN,
      dailyLossRemainingPct: NaN,
      aggregateOpenRiskPct: NaN,
      openPositionCount: openCount,
      maxConcurrentPositions: policy.maxConcurrentPositions,
      floatingPnl: Number.isFinite(floating) ? floating : NaN,
      equity: Number.isFinite(equity) ? equity : NaN,
      available: false,
    };
  }

  const peakRef =
    Number.isFinite(balance) && balance > equity ? balance : equity - (Number.isFinite(floating) ? Math.min(0, floating) : 0);
  const drawdownPct =
    Number.isFinite(peakRef) && peakRef > 0 && Number.isFinite(floating) && floating < 0
      ? (Math.abs(floating) / equity) * 100
      : Number.isFinite(equity) && Number.isFinite(balance) && balance > equity
        ? ((balance - equity) / balance) * 100
        : 0;

  const dailyLossUsedPct =
    Number.isFinite(today) && today < 0 ? (Math.abs(today) / equity) * 100 : 0;
  const dailyLossRemainingPct = Math.max(
    0,
    policy.dailyLossHaltPercent - dailyLossUsedPct,
  );

  // Open exposure proxy: floating loss relative to equity, capped by concurrent count.
  const aggregateOpenRiskPct =
    Number.isFinite(floating) && floating < 0
      ? (Math.abs(floating) / equity) * 100
      : openCount > 0
        ? Math.min(policy.maxAggregateOpenRiskPercent, policy.riskPerTradePercent)
        : 0;

  const auth = String(input.liveAuthorization || "").toUpperCase();
  const riskLocked = Boolean(input.riskLocked);
  const emergency = Boolean(input.emergencyStop);
  const maySubmit = input.ordersMaySubmit;

  let state: RiskHealthState = "Healthy";
  let reason = "Within owner risk ceilings.";

  if (emergency || riskLocked || dailyLossUsedPct >= policy.dailyLossHaltPercent) {
    state = "Halted";
    reason =
      dailyLossUsedPct >= policy.dailyLossHaltPercent
        ? `Daily loss reached the ${policy.dailyLossHaltPercent}% halt ceiling.`
        : emergency
          ? "Emergency stop is active on the trading session."
          : "Risk lock is active on this account session.";
  } else if (
    openCount > policy.maxConcurrentPositions ||
    aggregateOpenRiskPct >= policy.maxAggregateOpenRiskPercent ||
    (typeof maySubmit === "boolean" && maySubmit === false) ||
    auth.includes("DISABLED") ||
    auth.includes("BLOCK")
  ) {
    state = "Restricted";
    if (openCount > policy.maxConcurrentPositions) {
      reason = `Open positions exceed the max concurrent limit of ${policy.maxConcurrentPositions}.`;
    } else if (aggregateOpenRiskPct >= policy.maxAggregateOpenRiskPercent) {
      reason = `Aggregate open risk is at or above the ${policy.maxAggregateOpenRiskPercent}% ceiling.`;
    } else if (typeof maySubmit === "boolean" && maySubmit === false) {
      reason = "Orders may not submit under the current session authorization.";
    } else {
      reason = "Live trading authorization is not enabled for this session.";
    }
  } else if (
    dailyLossUsedPct >= policy.dailyLossHaltPercent * 0.5 ||
    drawdownPct >= 5 ||
    aggregateOpenRiskPct >= policy.maxAggregateOpenRiskPercent * 0.66
  ) {
    state = "Warning";
    reason =
      dailyLossUsedPct >= policy.dailyLossHaltPercent * 0.5
        ? `Daily loss usage is elevated (${dailyLossUsedPct.toFixed(1)}% of equity).`
        : drawdownPct >= 5
          ? `Current drawdown is elevated (${drawdownPct.toFixed(1)}%).`
          : `Open risk is elevated (${aggregateOpenRiskPct.toFixed(1)}% of equity).`;
  }

  return {
    state,
    reason,
    currentDrawdownPct: drawdownPct,
    dailyLossUsedPct,
    dailyLossRemainingPct,
    aggregateOpenRiskPct,
    openPositionCount: openCount,
    maxConcurrentPositions: policy.maxConcurrentPositions,
    floatingPnl: Number.isFinite(floating) ? floating : 0,
    equity,
    available: true,
  };
}
