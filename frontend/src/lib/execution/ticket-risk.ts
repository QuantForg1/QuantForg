/**
 * Order-ticket risk from the ticket's own numbers, checked against the owner
 * live limits (mirror of app/domain/institutional_trading/owner_live_limits.py).
 *
 * Planned risk = (|entry - SL| + spread + slippage) x contract x lots
 * + commission, rounded up to the cent. The 20% cap is rounded down.
 * Risk is never rounded down to pass. Reward:risk counts the spread once
 * on the risk leg: |TP - entry| / (|entry - SL| + spread) >= 0.50.
 *
 * 20% is a maximum PLANNED risk per trade, not a cap on realised loss: gaps
 * and execution failures can make a loss larger. Omitted commission is
 * unknown and is not treated as zero.
 */

export const OWNER_MAX_LOT = 0.01;
export const OWNER_MAX_PLANNED_RISK_PCT = 20;
export const OWNER_MIN_REWARD_RISK = 0.5;
export const OWNER_MAX_SPREAD = 1;
export const OWNER_SESSION_START_UTC_HOUR = 0;
/** 24 means the window runs through 23:59 UTC. There is no desk-hour close. */
export const OWNER_SESSION_END_UTC_HOUR = 24;
export const PLANNED_RISK_NOTE =
  "20% is the maximum planned risk per trade, not a cap on realised loss: " +
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
  /** Order deviation in price units. Omitted means zero, not an extra spread. */
  slippage?: number;
  /** Known commission in account currency. Omitted is unknown, not zero. */
  commission?: number;
  /** Price increment used to suggest a stop that fits the cap. */
  tickSize?: number;
  /** Defaults to now; injectable for tests. */
  now?: Date;
};

export type TicketRisk = {
  riskUsd: number | null;
  riskPctOfEquity: number | null;
  rewardRiskAfterSpread: number | null;
  maxSlRiskUsd: number;
  slDistance: number | null;
  tpDistance: number | null;
  fittedStopDistance: number | null;
  correction: string | null;
  violations: string[];
};

/** Round a monetary amount up to the cent. An exact cent stays on that cent. */
export function moneyUp(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Number((Math.ceil(Number((value * 100).toFixed(6))) / 100).toFixed(2));
}

/** Largest stop distance whose ceiling risk is still within `cap`. */
export function maximumAffordableStopDistance(params: {
  cap: number;
  spread: number;
  contractSize: number;
  lots: number;
  slippage?: number;
  commission?: number;
  tickSize?: number;
}): number | null {
  const slippage = Math.max(0, params.slippage ?? 0);
  const commission = Math.max(0, params.commission ?? 0);
  const spread = Math.max(0, params.spread);
  const tick = params.tickSize && params.tickSize > 0 ? params.tickSize : 0.001;
  const per = params.contractSize * params.lots;
  if (!(params.cap > 0) || !(per > 0)) return null;
  const room = params.cap - commission;
  if (room <= 0) return null;
  const raw = room / per - (spread + slippage);
  if (!(raw > 0)) return null;
  let steps = Math.floor((raw + 1e-9) / tick);
  let fitted = Number((steps * tick).toFixed(6));
  while (
    fitted > 0 &&
    moneyUp((fitted + spread + slippage) * per + commission) > params.cap + 1e-9
  ) {
    steps -= 1;
    fitted = Number((steps * tick).toFixed(6));
  }
  return fitted > 0 ? fitted : null;
}

function finitePositive(n: number): boolean {
  return Number.isFinite(n) && n > 0;
}

/** Per-trade planned-risk cap in USD: 20% of equity, rounded down to the cent. */
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
      slDistance: null,
      tpDistance: null,
      fittedStopDistance: null,
      correction: null,
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
  const slip = Number.isFinite(input.slippage) && (input.slippage ?? 0) > 0 ? (input.slippage as number) : 0;
  const commissionKnown = input.commission !== undefined && Number.isFinite(input.commission);
  const fee = commissionKnown && (input.commission as number) > 0 ? (input.commission as number) : 0;
  if (!commissionKnown) {
    violations.push("Commission unknown — inclusive planned risk is unverified");
  } else if ((input.commission as number) < 0) {
    violations.push("Commission cannot be negative");
  }
  if (!finitePositive(contractSize)) violations.push("Contract size unknown — cannot price risk");
  const riskUsd =
    commissionKnown &&
    (input.commission as number) >= 0 &&
    finitePositive(contractSize) &&
    finitePositive(lots) &&
    Number.isFinite(spr)
      ? moneyUp((slDist + spr + slip) * contractSize * lots + fee)
      : null;
  const riskPctOfEquity =
    riskUsd != null && finitePositive(equity) ? (riskUsd / equity) * 100 : null;
  let fittedStopDistance: number | null = null;
  let correction: string | null = null;
  if (riskUsd != null && finitePositive(equity) && riskUsd > cap + 1e-9) {
    fittedStopDistance =
      Number.isFinite(spr)
        ? maximumAffordableStopDistance({
            cap,
            spread: spr,
            contractSize,
            lots,
            slippage: slip,
            commission: fee,
            tickSize: input.tickSize,
          })
        : null;
    if (fittedStopDistance == null) {
      const bare = moneyUp((spr + slip) * contractSize * lots + fee);
      correction =
        `Minimum volume ${lots} costs $${bare.toFixed(2)} before any protective stop, ` +
        `which is above the owner cap $${cap.toFixed(2)}. No smaller lot is allowed, ` +
        "so this order cannot be submitted.";
    } else {
      correction =
        `Tighten the stop to ${fittedStopDistance} or less so planned risk fits ` +
        `$${cap.toFixed(2)}. The lot cannot be reduced below ${lots}.`;
    }
    violations.push(
      `Planned risk $${riskUsd.toFixed(2)} > owner cap $${cap.toFixed(2)} ` +
        `(${OWNER_MAX_PLANNED_RISK_PCT}% of equity). ${correction}`,
    );
  }
  const rewardRiskAfterSpread = Number.isFinite(spr) ? tpDist / (slDist + spr) : null;
  if (rewardRiskAfterSpread != null && rewardRiskAfterSpread < OWNER_MIN_REWARD_RISK)
    violations.push(
      `Reward:risk after spread ${rewardRiskAfterSpread.toFixed(2)} < ${OWNER_MIN_REWARD_RISK.toFixed(2)}`,
    );
  return {
    riskUsd,
    riskPctOfEquity,
    rewardRiskAfterSpread,
    maxSlRiskUsd: cap,
    slDistance: slDist,
    tpDistance: tpDist,
    fittedStopDistance,
    correction,
    violations,
  };
}
