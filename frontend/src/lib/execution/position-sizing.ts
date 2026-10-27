/** Client helpers for risk-based lot sizing (display / ticket sync). */

export type SizingMode = "percentage_risk" | "fixed_lot";

/** Absolute stop distance from entry and SL prices. */
export function stopLossDistance(
  entry: number,
  stopLoss: number,
): number | null {
  if (!Number.isFinite(entry) || !Number.isFinite(stopLoss) || entry <= 0) {
    return null;
  }
  const d = Math.abs(entry - stopLoss);
  return d > 0 ? d : null;
}

/**
 * Lots that fit equity · risk% · stop · spread · slippage · contract.
 * Floors to the lot step. Returns null when the broker minimum lot does not
 * fit. Never rounds a sub-minimum result up to the minimum lot.
 * Risk is ceiling-rounded to the cent, matching ticket-risk.ts.
 */
function moneyUp(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Number((Math.ceil(Number((value * 100).toFixed(6))) / 100).toFixed(2));
}

function moneyDown(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.floor(value * 100 + 1e-9) / 100;
}

export function lotsFromRiskBudget(params: {
  equity: number;
  riskPct: number;
  stopDistance: number;
  contractSize?: number;
  minLot?: number;
  maxLot?: number;
  lotStep?: number;
  spread?: number;
  slippage?: number;
  commission?: number;
  /** Saved cap in account currency. The sizing budget cannot exceed it. */
  maxRiskUsd?: number;
}): number | null {
  const {
    equity,
    riskPct,
    stopDistance,
    contractSize = 100,
    minLot = 0.01,
    maxLot = 10,
    lotStep = 0.01,
    spread = 0,
    slippage = 0,
    commission = 0,
    maxRiskUsd,
  } = params;
  if (
    !Number.isFinite(equity) ||
    equity <= 0 ||
    !Number.isFinite(riskPct) ||
    riskPct <= 0 ||
    !Number.isFinite(stopDistance) ||
    stopDistance <= 0 ||
    !Number.isFinite(contractSize) ||
    contractSize <= 0 ||
    !Number.isFinite(spread) ||
    spread < 0 ||
    !Number.isFinite(slippage) ||
    slippage < 0 ||
    !Number.isFinite(commission) ||
    commission < 0 ||
    !Number.isFinite(minLot) ||
    minLot <= 0 ||
    !Number.isFinite(lotStep) ||
    lotStep <= 0 ||
    !Number.isFinite(maxLot) ||
    maxLot < minLot
  ) {
    return null;
  }
  const per = stopDistance + spread + slippage;
  if (per <= 0) return null;
  const requested = equity * (riskPct / 100);
  const budget =
    maxRiskUsd != null && Number.isFinite(maxRiskUsd) ? Math.min(requested, maxRiskUsd) : requested;
  const room = moneyDown(budget) - commission;
  if (room <= 0) return null;
  const raw = room / (per * contractSize);
  if (!Number.isFinite(raw) || raw <= 0) return null;
  let lots = Math.floor((raw + 1e-12) / lotStep) * lotStep;
  lots = Math.min(maxLot, lots);
  const cap = moneyDown(budget);
  while (lots + 1e-9 >= minLot) {
    const risk = moneyUp(per * contractSize * lots + commission);
    if (risk <= cap + 1e-9) return Number(lots.toFixed(2));
    lots = Number((lots - lotStep).toFixed(8));
  }
  return null;
}

/** Floor volume onto the lot step. Null when it cannot meet the minimum. */
export function normalizeLot(
  volume: number,
  step = 0.01,
  min = 0.01,
  max = 0.01,
): number | null {
  if (!Number.isFinite(volume) || volume <= 0 || step <= 0 || min <= 0 || max < min) {
    return null;
  }
  const stepped = Math.floor((volume + 1e-9) / step) * step;
  const capped = Math.min(max, stepped);
  if (capped + 1e-9 < min) return null;
  return Number(capped.toFixed(2));
}

export function contractSizeForSymbol(symbol: string): number {
  const u = symbol.trim().toUpperCase();
  if (u.startsWith("XAU") || u.includes("GOLD")) return 100;
  if (u.startsWith("XAG") || u.includes("SILVER")) return 5000;
  if (u.includes("BTC") || u.includes("ETH")) return 1;
  return 100_000;
}
