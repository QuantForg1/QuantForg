/** Operator-facing BUY / SELL / WAIT headlines. Never fabricates a side. */

export type SignalPipeline = {
  market: string;
  data: string;
  buy_score: number;
  sell_score: number;
  decision: string;
  first_blocker: string | null;
  sniper: string;
  risk: string;
  safety: string;
  optimizer: string;
  oms: string;
  opportunity_score: number;
  opportunity_threshold: number;
  execution_lifecycle: string | null;
};

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

export function parseSignalPipeline(raw: unknown): SignalPipeline | null {
  if (!raw || typeof raw !== "object") return null;
  const row = raw as Record<string, unknown>;
  const num = (v: unknown) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  };
  const text = (v: unknown, fallback: string) => {
    const s = String(v ?? "").trim();
    return s || fallback;
  };
  const blocker = row.first_blocker;
  return {
    market: text(row.market, "UNKNOWN"),
    data: text(row.data, "UNKNOWN"),
    buy_score: num(row.buy_score),
    sell_score: num(row.sell_score),
    decision: text(row.decision, "WAIT"),
    first_blocker:
      blocker == null || blocker === "" ? null : String(blocker),
    sniper: text(row.sniper, "NOT_RUN"),
    risk: text(row.risk, "NOT_REACHED"),
    safety: text(row.safety, "NOT_REACHED"),
    optimizer: text(row.optimizer, "NOT_REACHED"),
    oms: text(row.oms, "NOT_REACHED"),
    opportunity_score: num(row.opportunity_score),
    opportunity_threshold: num(row.opportunity_threshold) || 70,
    execution_lifecycle:
      row.execution_lifecycle == null || row.execution_lifecycle === ""
        ? null
        : String(row.execution_lifecycle),
  };
}

export function formatFirstBlocker(code: string | null | undefined): string {
  const token = String(code || "").trim();
  return token ? `First blocker: ${token}` : "";
}
