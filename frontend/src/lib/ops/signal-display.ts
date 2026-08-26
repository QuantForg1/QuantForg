/** Operator-facing BUY / SELL / WAIT headlines. Never fabricates a side. */

export function formatSignalHeadline(
  direction: string,
  reason?: string | null,
): string {
  const action = (direction || "").trim().toUpperCase();
  const text = (reason || "").trim();
  if (action === "WAIT") {
    if (!text) return "WAIT — setup not confirmed";
    return text.toUpperCase().startsWith("WAIT") ? text : `WAIT — ${text}`;
  }
  if (action === "BUY") {
    return text || "BUY — sniper setup confirmed";
  }
  if (action === "SELL") {
    return text || "SELL — bearish liquidity sweep + BOS";
  }
  return text || action || "NO_TRADE";
}

export function signalDirectionGlyph(
  direction: string,
): "BUY" | "SELL" | "WAIT" | "NONE" {
  const action = (direction || "").trim().toUpperCase();
  if (action === "BUY" || action === "SELL" || action === "WAIT") return action;
  return "NONE";
}
