/** Operator-facing BUY / SELL / WAIT headlines. Never fabricates a side. */

export type SignalPipeline = {
  market: string;
  data: string;
  buy_score: number;
  sell_score: number;
  candidate: string;
  decision: string;
  final_decision: string;
  first_blocker: string | null;
  sniper: string;
  risk: string;
  safety: string;
  optimizer: string;
  oms: string;
  broker: string;
  mt5: string;
  opportunity_score: number;
  opportunity_threshold: number;
  opportunity_gate: string;
  setup_state: string;
  sniper_tier: string | null;
  market_regime: string | null;
  entry_state: string | null;
  zone_timeframe: string | null;
  atr_timeframe: string | null;
  execution_lifecycle: string | null;
  chase_distance: string | null;
  buy_components: Record<string, number>;
  sell_components: Record<string, number>;
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

function asScoreMap(raw: unknown): Record<string, number> {
  if (!raw || typeof raw !== "object") return {};
  const out: Record<string, number> = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    const n = Number(value);
    if (Number.isFinite(n)) out[key] = n;
  }
  return out;
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
  const decision = text(row.decision, "WAIT");
  const takeFallback =
    decision === "BUY" || decision === "SELL" ? "TAKE" : "WAIT";
  return {
    market: text(row.market, "UNKNOWN"),
    data: text(row.data, "UNKNOWN"),
    buy_score: num(row.buy_score),
    sell_score: num(row.sell_score),
    candidate: text(row.candidate, "NONE"),
    decision,
    final_decision: text(row.final_decision, takeFallback),
    first_blocker:
      blocker == null || blocker === "" ? null : String(blocker),
    sniper: text(row.sniper, "NOT_RUN"),
    risk: text(row.risk, "NOT_REACHED"),
    safety: text(row.safety, "NOT_REACHED"),
    optimizer: text(row.optimizer, "NOT_REACHED"),
    oms: text(row.oms, "NOT_REACHED"),
    broker: text(row.broker, "NOT_REACHED"),
    mt5: text(row.mt5, "NOT_REACHED"),
    opportunity_score: num(row.opportunity_score),
    opportunity_threshold: num(row.opportunity_threshold) || 70,
    opportunity_gate: text(row.opportunity_gate, "WAIT"),
    setup_state: text(row.setup_state, "WAIT"),
    sniper_tier:
      row.sniper_tier == null || row.sniper_tier === ""
        ? null
        : String(row.sniper_tier),
    market_regime:
      row.market_regime == null || row.market_regime === ""
        ? null
        : String(row.market_regime),
    entry_state:
      row.entry_state == null || row.entry_state === ""
        ? null
        : String(row.entry_state),
    zone_timeframe:
      row.zone_timeframe == null || row.zone_timeframe === ""
        ? null
        : String(row.zone_timeframe),
    atr_timeframe:
      row.atr_timeframe == null || row.atr_timeframe === ""
        ? null
        : String(row.atr_timeframe),
    execution_lifecycle:
      row.execution_lifecycle == null || row.execution_lifecycle === ""
        ? null
        : String(row.execution_lifecycle),
    chase_distance:
      row.chase_distance == null || row.chase_distance === ""
        ? null
        : String(row.chase_distance),
    buy_components: asScoreMap(row.buy_components),
    sell_components: asScoreMap(row.sell_components),
  };
}

export function formatFirstBlocker(code: string | null | undefined): string {
  const token = String(code || "").trim();
  return token ? `First blocker: ${token}` : "";
}
