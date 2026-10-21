/**
 * Owner live limits (2026-10-20): every new entry needs a broker-side stop
 * loss AND take profit. The ticket blocks submit until both are set.
 */

function isPositivePrice(value: string | null | undefined): boolean {
  const raw = (value ?? "").trim();
  if (!raw) return false;
  const n = Number(raw);
  return Number.isFinite(n) && n > 0;
}

/** Null when both stops are valid, otherwise the reason submit is blocked. */
export function protectiveStopsError(
  stopLoss: string | null | undefined,
  takeProfit: string | null | undefined,
): string | null {
  const slOk = isPositivePrice(stopLoss);
  const tpOk = isPositivePrice(takeProfit);
  if (!slOk && !tpOk) return "Stop loss and take profit are required";
  if (!slOk) return "Stop loss is required";
  if (!tpOk) return "Take profit is required";
  return null;
}
