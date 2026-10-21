/**
 * Order-ticket risk from the ticket's own numbers, checked against the owner
 * live limits (mirror of app/domain/institutional_trading/owner_live_limits.py).
 *
 * Planned SL loss = |entry - SL| x contract size x lots. Reward:risk counts the
 * spread once on the risk leg: |TP - entry| / (|entry - SL| + spread).
 */

export const OWNER_MAX_LOT = 0.01;
export const OWNER_MIN_SL_RISK_USD = 1.5;
export const OWNER_MAX_SL_RISK_USD = 2.0;
export const OWNER_MIN_REWARD_RISK = 1.5;
const OWNER_SL_RISK_PCT = 2.0;
const OWNER_SL_RISK_PCT_EQUITY_THRESHOLD = 100;

export type TicketRiskInput = {
  side: "buy" | "sell";
  entry: number;
  stopLoss: number;
  takeProfit: number;
  lots: number;
  contractSize: number;
  equity: number;
  spread: number;
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

/** Per-trade SL-loss cap in USD: $2.00, or 2% of equity when that is lower above $100. */
export function maxSlRiskUsd(equity: number): number {
  let cap = OWNER_MAX_SL_RISK_USD;
  if (Number.isFinite(equity) && equity > OWNER_SL_RISK_PCT_EQUITY_THRESHOLD) {
    const pctCap = Math.floor(equity * OWNER_SL_RISK_PCT) / 100;
    cap = Math.min(cap, pctCap);
  }
  return cap;
}

export function ticketRisk(input: TicketRiskInput): TicketRisk {
  const { side, entry, stopLoss, takeProfit, lots, contractSize, equity, spread } = input;
  const cap = maxSlRiskUsd(equity);
  const violations: string[] = [];
  if (!finitePositive(lots)) violations.push("Volume is required");
  else if (lots > OWNER_MAX_LOT + 1e-9)
    violations.push(`Volume ${lots} exceeds owner max ${OWNER_MAX_LOT} lot`);
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

  const slDist = Math.abs(entry - stopLoss);
  const tpDist = Math.abs(takeProfit - entry);
  const riskUsd =
    finitePositive(contractSize) && finitePositive(lots)
      ? Math.round(slDist * contractSize * lots * 100) / 100
      : null;
  const riskPctOfEquity =
    riskUsd != null && finitePositive(equity) ? (riskUsd / equity) * 100 : null;
  if (riskUsd != null) {
    if (riskUsd > cap)
      violations.push(`Planned SL loss $${riskUsd.toFixed(2)} > owner cap $${cap.toFixed(2)}`);
    else if (riskUsd <= OWNER_MIN_SL_RISK_USD)
      violations.push(
        `Planned SL loss $${riskUsd.toFixed(2)} must be above $${OWNER_MIN_SL_RISK_USD.toFixed(2)}`,
      );
  }
  const spr = Number.isFinite(spread) && spread >= 0 ? spread : NaN;
  const rewardRiskAfterSpread = Number.isFinite(spr) ? tpDist / (slDist + spr) : null;
  if (rewardRiskAfterSpread == null) violations.push("Spread unknown — cannot verify reward:risk");
  else if (rewardRiskAfterSpread < OWNER_MIN_REWARD_RISK)
    violations.push(
      `Reward:risk after spread ${rewardRiskAfterSpread.toFixed(2)} < ${OWNER_MIN_REWARD_RISK.toFixed(2)}`,
    );
  return { riskUsd, riskPctOfEquity, rewardRiskAfterSpread, maxSlRiskUsd: cap, violations };
}
