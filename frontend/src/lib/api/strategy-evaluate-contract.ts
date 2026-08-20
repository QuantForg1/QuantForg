/**
 * POST /strategy/evaluate field contract — no framework imports.
 * Extra fields (side, volume) are rejected by the backend (extra=forbid).
 */

export const STRATEGY_EVALUATE_FORBIDDEN = ["side", "volume"] as const;
export const STRATEGY_EVALUATE_REQUIRED = ["request_id", "symbol"] as const;

export function mapStrategyEvaluateAliases(
  input: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = { ...input };
  if (!out.requested_lots && out.volume != null) {
    out.requested_lots = out.volume;
  }
  for (const field of STRATEGY_EVALUATE_FORBIDDEN) {
    delete out[field];
  }
  return out;
}

export function assertStrategyEvaluateShape(body: Record<string, unknown>): void {
  for (const key of STRATEGY_EVALUATE_REQUIRED) {
    const value = typeof body[key] === "string" ? body[key].trim() : "";
    if (!value) {
      throw new Error(`strategy/evaluate requires ${key}`);
    }
  }
  for (const field of STRATEGY_EVALUATE_FORBIDDEN) {
    if (field in body) {
      throw new Error(`strategy/evaluate rejects unknown field '${field}'`);
    }
  }
}
