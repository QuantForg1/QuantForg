/**
 * Read-only display of the production owner hard ceilings.
 * These values must mirror LIVE policy — never reinterpret or soften them here.
 * Dashboard risk intelligence uses this for explanation only; enforcement stays
 * in the existing risk engine / OMS path.
 */
export const OWNER_RISK_POLICY_DISPLAY = {
  maxLot: 0.01,
  riskPerTradePercent: 20,
  absoluteRiskCeilingPercent: 20,
  minimumNetRewardRisk: 0.2,
  preferredRewardRisk: 0.5,
  minimumTradeQuality: 70,
  maxConcurrentPositions: 1,
  dailyLossHaltPercent: 48,
  maxAggregateOpenRiskPercent: 30,
  mandatoryStopLoss: true,
  gridTrading: false,
  martingale: false,
  averagingDown: false,
  m1LiveSubmissions: false,
} as const;

export type OwnerRiskPolicyDisplay = typeof OWNER_RISK_POLICY_DISPLAY;
