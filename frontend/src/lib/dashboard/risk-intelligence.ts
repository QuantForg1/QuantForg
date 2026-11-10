/**
 * Derive account risk intelligence from live session + open exposure.
 * Thresholds mirror production ceilings for display math only — does not
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
  /** Optional personal/effective ceilings; defaults stay internal. */
  dailyLossHaltPercent?: number;
  maxAggregateOpenRiskPercent?: number;
  maxConcurrentPositions?: number;
  riskPerTradePercent?: number;
}): RiskIntelligenceSnapshot {
  const equity = num(input.equity);
  const balance = num(input.balance);
  const floating = num(input.floatingPnl);
  const today = num(input.todayPnl);
  const openCount = Math.max(0, Math.floor(input.openPositionCount ?? 0));
  const policy = OWNER_RISK_POLICY_DISPLAY;
  const dailyHalt =
    Number.isFinite(input.dailyLossHaltPercent)
      ? Number(input.dailyLossHaltPercent)
      : policy.dailyLossHaltPercent;
  const aggCeiling =
    Number.isFinite(input.maxAggregateOpenRiskPercent)
      ? Number(input.maxAggregateOpenRiskPercent)
      : policy.maxAggregateOpenRiskPercent;
  const maxConcurrent =
    Number.isFinite(input.maxConcurrentPositions)
      ? Math.max(1, Math.floor(Number(input.maxConcurrentPositions)))
      : policy.maxConcurrentPositions;
  const riskPerTrade =
    Number.isFinite(input.riskPerTradePercent)
      ? Number(input.riskPerTradePercent)
      : policy.riskPerTradePercent;

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
      maxConcurrentPositions: maxConcurrent,
      floatingPnl: Number.isFinite(floating) ? floating : NaN,
      equity: Number.isFinite(equity) ? equity : NaN,
      available: false,
    };
  }

  const peakRef =
    Number.isFinite(balance) && balance > equity
      ? balance
      : equity - (Number.isFinite(floating) ? Math.min(0, floating) : 0);
  const drawdownPct =
    Number.isFinite(peakRef) && peakRef > 0 && Number.isFinite(floating) && floating < 0
      ? (Math.abs(floating) / equity) * 100
      : Number.isFinite(equity) && Number.isFinite(balance) && balance > equity
        ? ((balance - equity) / balance) * 100
        : 0;

  const dailyLossUsedPct =
    Number.isFinite(today) && today < 0 ? (Math.abs(today) / equity) * 100 : 0;
  const dailyLossRemainingPct = Math.max(0, dailyHalt - dailyLossUsedPct);

  const aggregateOpenRiskPct =
    Number.isFinite(floating) && floating < 0
      ? (Math.abs(floating) / equity) * 100
      : openCount > 0
        ? Math.min(aggCeiling, riskPerTrade)
        : 0;

  const auth = String(input.liveAuthorization || "").toUpperCase();
  const riskLocked = Boolean(input.riskLocked);
  const emergency = Boolean(input.emergencyStop);
  const maySubmit = input.ordersMaySubmit;

  let state: RiskHealthState = "Healthy";
  let reason = "Account risk is within your effective protection limits.";

  if (emergency || riskLocked || dailyLossUsedPct >= dailyHalt) {
    state = "Halted";
    reason =
      dailyLossUsedPct >= dailyHalt
        ? "Daily loss protection has halted new entries for this account."
        : emergency
          ? "Emergency stop is active on the trading session."
          : "Risk lock is active on this account session.";
  } else if (
    openCount > maxConcurrent ||
    aggregateOpenRiskPct >= aggCeiling ||
    (typeof maySubmit === "boolean" && maySubmit === false) ||
    auth.includes("DISABLED") ||
    auth.includes("BLOCK")
  ) {
    state = "Restricted";
    if (openCount > maxConcurrent) {
      reason = "Open positions exceed your allowed concurrent-position preference.";
    } else if (aggregateOpenRiskPct >= aggCeiling) {
      reason = "Aggregate open risk is at or above your effective ceiling.";
    } else if (typeof maySubmit === "boolean" && maySubmit === false) {
      reason = "Orders may not submit under the current session authorization.";
    } else {
      reason = "Live trading authorization is not enabled for this session.";
    }
  } else if (
    dailyLossUsedPct >= dailyHalt * 0.5 ||
    drawdownPct >= 5 ||
    aggregateOpenRiskPct >= aggCeiling * 0.66
  ) {
    state = "Warning";
    reason =
      dailyLossUsedPct >= dailyHalt * 0.5
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
    maxConcurrentPositions: maxConcurrent,
    floatingPnl: Number.isFinite(floating) ? floating : 0,
    equity,
    available: true,
  };
}
