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
 * Approximate lots from equity · risk% · stop distance · contract size.
 * Risk Engine remains authoritative — this mirrors PERCENTAGE_RISK for UI sync.
 */
export function lotsFromRiskBudget(params: {
  equity: number;
  riskPct: number;
  stopDistance: number;
  contractSize?: number;
  minLot?: number;
  maxLot?: number;
  lotStep?: number;
}): number | null {
  const {
    equity,
    riskPct,
    stopDistance,
    contractSize = 100,
    minLot = 0.01,
    maxLot = 10,
    lotStep = 0.01,
  } = params;
  if (
    !Number.isFinite(equity) ||
    equity <= 0 ||
    !Number.isFinite(riskPct) ||
    riskPct <= 0 ||
    !Number.isFinite(stopDistance) ||
    stopDistance <= 0 ||
    !Number.isFinite(contractSize) ||
    contractSize <= 0
  ) {
    return null;
  }
  const budget = equity * (riskPct / 100);
  const raw = budget / (stopDistance * contractSize);
  if (!Number.isFinite(raw) || raw <= 0) return null;
  const stepped = Math.floor(raw / lotStep) * lotStep;
  const capped = Math.min(maxLot, Math.max(minLot, stepped));
  return Number(capped.toFixed(2));
}

export function contractSizeForSymbol(symbol: string): number {
  const u = symbol.trim().toUpperCase();
  if (u.startsWith("XAU") || u.includes("GOLD")) return 100;
  if (u.startsWith("XAG") || u.includes("SILVER")) return 5000;
  if (u.includes("BTC") || u.includes("ETH")) return 1;
  return 100_000;
}
