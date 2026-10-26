/**
 * Order-ticket risk from the ticket's own numbers, checked against the owner
 * live limits (mirror of app/domain/institutional_trading/owner_live_limits.py).
 *
 * Planned risk = (|entry - SL| + spread) x contract size x lots, capped at 9%
 * of live equity. Reward:risk counts the spread once on the risk leg:
 * |TP - entry| / (|entry - SL| + spread) >= 1.5.
 *
 * 9% is a maximum PLANNED risk, not a cap on realised loss: slippage, gaps,
 * commissions and execution failures can make a loss larger.
 */

export const OWNER_MAX_LOT = 0.01;
export const OWNER_MAX_PLANNED_RISK_PCT = 9;
export const OWNER_MIN_REWARD_RISK = 1.5;
export const OWNER_MAX_SPREAD = 0.45;
export const OWNER_SESSION_START_UTC_HOUR = 0;
/** 24 means the window runs through 23:59 UTC. There is no desk-hour close. */
export const OWNER_SESSION_END_UTC_HOUR = 24;
export const PLANNED_RISK_NOTE =
  "9% is the maximum planned risk per trade, not a cap on realised loss: " +
  "slippage, gaps, commissions and execution failures can make a loss larger.";

export type TicketRiskInput = {
  side: "buy" | "sell";
  entry: number;
  stopLoss: number;
  takeProfit: number;
  lots: number;
  contractSize: number;
  equity: number;
  spread: number;
  /** Defaults to now; injectable for tests. */
  now?: Date;
};

export type TicketRisk = {
  riskUsd: number | null;
  riskPctOfEquity: number | null;
  rewardRiskAfterSpread: number | null;
  maxSlRiskUsd: number;
  violations: string[];
};

function finitePositive(n: number): boolean {
  return Number.isFinite(n) && n > 0;
}

/** Per-trade planned-risk cap in USD: 9% of equity, rounded down to the cent. */
export function maxSlRiskUsd(equity: number): number {
  if (!finitePositive(equity)) return 0;
  return Math.floor(equity * OWNER_MAX_PLANNED_RISK_PCT + 1e-9) / 100;
}

export function inOwnerSession(now: Date = new Date()): boolean {
  if (Number.isNaN(now.getTime())) return false;
  const minute = now.getUTCHours() * 60 + now.getUTCMinutes();
  const start = OWNER_SESSION_START_UTC_HOUR * 60;
  const end =
    OWNER_SESSION_END_UTC_HOUR >= 24 ? 24 * 60 : OWNER_SESSION_END_UTC_HOUR * 60;
  return minute >= start && minute < end;
}

export function ticketRisk(input: TicketRiskInput): TicketRisk {
  const { side, entry, stopLoss, takeProfit, lots, contractSize, equity, spread } = input;
  const cap = maxSlRiskUsd(equity);
  const violations: string[] = [];
  if (!finitePositive(lots)) violations.push("Volume is required");
  else if (lots > OWNER_MAX_LOT + 1e-9)
    violations.push(`Volume ${lots} exceeds owner max ${OWNER_MAX_LOT} lot`);
  if (!finitePositive(equity)) violations.push("Equity unavailable — cannot size risk");
  if (!inOwnerSession(input.now))
    violations.push("Entries only 00:00–23:59 UTC");
  if (!finitePositive(entry) || !finitePositive(stopLoss) || !finitePositive(takeProfit)) {
    violations.push("Entry, stop loss and take profit are required");
    return {
      riskUsd: null,
      riskPctOfEquity: null,
      rewardRiskAfterSpread: null,
      maxSlRiskUsd: cap,
      violations,
    };
  }
  const slOk = side === "buy" ? stopLoss < entry : stopLoss > entry;
  const tpOk = side === "buy" ? takeProfit > entry : takeProfit < entry;
  if (!slOk || !tpOk) violations.push("Stop loss / take profit on the wrong side of entry");

  const spr = Number.isFinite(spread) && spread >= 0 ? spread : NaN;
  if (!Number.isFinite(spr)) violations.push("Spread unknown — cannot verify risk");
  else if (spr > OWNER_MAX_SPREAD + 1e-9)
    violations.push(`Spread ${spr.toFixed(3)} > max ${OWNER_MAX_SPREAD.toFixed(2)}`);

  const slDist = Math.abs(entry - stopLoss);
  const tpDist = Math.abs(takeProfit - entry);
  const riskUsd =
    finitePositive(contractSize) && finitePositive(lots) && Number.isFinite(spr)
      ? Math.round((slDist + spr) * contractSize * lots * 100) / 100
      : null;
  const riskPctOfEquity =
    riskUsd != null && finitePositive(equity) ? (riskUsd / equity) * 100 : null;
  if (riskUsd != null && finitePositive(equity) && riskUsd > cap + 1e-9)
    violations.push(
      `Planned risk $${riskUsd.toFixed(2)} > owner cap $${cap.toFixed(2)} ` +
        `(${OWNER_MAX_PLANNED_RISK_PCT}% of equity)`,
    );
  const rewardRiskAfterSpread = Number.isFinite(spr) ? tpDist / (slDist + spr) : null;
  if (rewardRiskAfterSpread != null && rewardRiskAfterSpread < OWNER_MIN_REWARD_RISK)
    violations.push(
      `Reward:risk after spread ${rewardRiskAfterSpread.toFixed(2)} < ${OWNER_MIN_REWARD_RISK.toFixed(2)}`,
    );
  return { riskUsd, riskPctOfEquity, rewardRiskAfterSpread, maxSlRiskUsd: cap, violations };
}
