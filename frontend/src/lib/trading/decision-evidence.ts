/**
 * Display helpers for Decision Evidence.
 * Values come from the read-only report API. Missing values stay missing.
 */

export const DECISION_EVIDENCE_NOT_AVAILABLE = "Not available";
export const DECISION_EVIDENCE_AWAITING = "Awaiting engine evidence";

export function evidenceText(value: unknown): string {
  if (value == null) return DECISION_EVIDENCE_NOT_AVAILABLE;
  const text = String(value).trim();
  if (!text) return DECISION_EVIDENCE_NOT_AVAILABLE;
  return text;
}

export function decisionTone(decision: string): "buy" | "sell" | "neutral" {
  if (decision === "BUY") return "buy";
  if (decision === "SELL") return "sell";
  return "neutral";
}

/** A decision word is never treated as proof of an order. */
export function orderExecutionLabel(input: {
  orderExecuted?: unknown;
  orderSent?: unknown;
}): string {
  if (input.orderExecuted === true) return "Order filled";
  if (input.orderSent === true) return "Order sent — fill not recorded";
  return "Not executed";
}
