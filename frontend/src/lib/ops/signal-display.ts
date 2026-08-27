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
  independent_evidence: string[];
  confluence_class: string | null;
  directional_edge: number | null;
  edge_margin: number | null;
  ltf_buy_score: number | null;
  ltf_sell_score: number | null;
  structure_timeframe: string | null;
  entry_timeframe: string | null;
  signal_age_ms: number | null;
  zone_age_ms: number | null;
  bars_since_structure_event: number | null;
  structure_score_xy: string | null;
  liquidity_score_xy: string | null;
  zone_score_xy: string | null;
  displacement_score_xy: string | null;
  timing_score_xy: string | null;
  rr_score_xy: string | null;
  freshness: string | null;
  h1_context: string | null;
  eligibility_status: string | null;
  eligibility_reason: string | null;
  blocker_category: string | null;
  blocker_reason: string | null;
  execution_stage: string | null;
  optimizer_status: string | null;
  oms_status: string | null;
  forwarded_to_oms: boolean | null;
  broker_status: string | null;
  mt5_status: string | null;
  ticket: string | number | null;
  reject_burst: Record<string, unknown> | null;
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
    independent_evidence: Array.isArray(row.independent_evidence)
      ? (row.independent_evidence as unknown[]).map((v) => String(v))
      : [],
    confluence_class:
      row.confluence_class == null || row.confluence_class === ""
        ? null
        : String(row.confluence_class),
    directional_edge: Number.isFinite(Number(row.directional_edge))
      ? Number(row.directional_edge)
      : null,
    edge_margin: Number.isFinite(Number(row.edge_margin))
      ? Number(row.edge_margin)
      : null,
    ltf_buy_score: Number.isFinite(Number(row.ltf_buy_score))
      ? Number(row.ltf_buy_score)
      : null,
    ltf_sell_score: Number.isFinite(Number(row.ltf_sell_score))
      ? Number(row.ltf_sell_score)
      : null,
    structure_timeframe:
      row.structure_timeframe == null || row.structure_timeframe === ""
        ? null
        : String(row.structure_timeframe),
    entry_timeframe:
      row.entry_timeframe == null || row.entry_timeframe === ""
        ? null
        : String(row.entry_timeframe),
    signal_age_ms: Number.isFinite(Number(row.signal_age_ms))
      ? Number(row.signal_age_ms)
      : null,
    zone_age_ms: Number.isFinite(Number(row.zone_age_ms))
      ? Number(row.zone_age_ms)
      : null,
    bars_since_structure_event: Number.isFinite(
      Number(row.bars_since_structure_event),
    )
      ? Number(row.bars_since_structure_event)
      : null,
    structure_score_xy:
      row.structure_score_xy == null || row.structure_score_xy === ""
        ? null
        : String(row.structure_score_xy),
    liquidity_score_xy:
      row.liquidity_score_xy == null || row.liquidity_score_xy === ""
        ? null
        : String(row.liquidity_score_xy),
    zone_score_xy:
      row.zone_score_xy == null || row.zone_score_xy === ""
        ? null
        : String(row.zone_score_xy),
    displacement_score_xy:
      row.displacement_score_xy == null || row.displacement_score_xy === ""
        ? null
        : String(row.displacement_score_xy),
    timing_score_xy:
      row.timing_score_xy == null || row.timing_score_xy === ""
        ? null
        : String(row.timing_score_xy),
    rr_score_xy:
      row.rr_score_xy == null || row.rr_score_xy === ""
        ? null
        : String(row.rr_score_xy),
    freshness:
      row.freshness == null || row.freshness === ""
        ? null
        : String(row.freshness),
    h1_context:
      row.h1_context == null || row.h1_context === ""
        ? "context-only"
        : String(row.h1_context),
    eligibility_status:
      row.eligibility_status == null || row.eligibility_status === ""
        ? null
        : String(row.eligibility_status),
    eligibility_reason:
      row.eligibility_reason == null || row.eligibility_reason === ""
        ? null
        : String(row.eligibility_reason),
    blocker_category:
      row.blocker_category == null || row.blocker_category === ""
        ? null
        : String(row.blocker_category),
    blocker_reason:
      row.blocker_reason == null || row.blocker_reason === ""
        ? null
        : String(row.blocker_reason),
    execution_stage:
      row.execution_stage == null || row.execution_stage === ""
        ? null
        : String(row.execution_stage),
    optimizer_status:
      row.optimizer_status == null || row.optimizer_status === ""
        ? row.optimizer == null || row.optimizer === ""
          ? null
          : String(row.optimizer)
        : String(row.optimizer_status),
    oms_status:
      row.oms_status == null || row.oms_status === ""
        ? row.oms == null || row.oms === ""
          ? null
          : String(row.oms)
        : String(row.oms_status),
    forwarded_to_oms:
      row.forwarded_to_oms == null || row.forwarded_to_oms === ""
        ? null
        : Boolean(row.forwarded_to_oms),
    broker_status:
      row.broker_status == null || row.broker_status === ""
        ? row.broker == null || row.broker === ""
          ? null
          : String(row.broker)
        : String(row.broker_status),
    mt5_status:
      row.mt5_status == null || row.mt5_status === ""
        ? row.mt5 == null || row.mt5 === ""
          ? null
          : String(row.mt5)
        : String(row.mt5_status),
    ticket:
      row.ticket == null || row.ticket === ""
        ? null
        : (row.ticket as string | number),
    reject_burst:
      row.reject_burst && typeof row.reject_burst === "object"
        ? (row.reject_burst as Record<string, unknown>)
        : null,
  };
}

export function formatFirstBlocker(code: string | null | undefined): string {
  const token = String(code || "").trim();
  return token ? `First blocker: ${token}` : "";
}

const BLOCKER_CATEGORIES = [
  "RISK_REJECTED",
  "EXECUTION_REJECT_BURST",
  "SAFETY_BLOCKED",
  "OMS_REJECTED",
  "BROKER_REJECTED",
  "MT5_REJECTED",
] as const;

export type ExecutionBlockerCategory = (typeof BLOCKER_CATEGORIES)[number];

export function classifyExecutionBlocker(
  code: string | null | undefined,
): ExecutionBlockerCategory | null {
  const token = String(code || "").trim().toUpperCase();
  if (!token) return null;
  if (
    token.includes("EXECUTION_REJECT_BURST") ||
    token.includes("REJECT_BURST") ||
    token === "ENTRY_BURST" ||
    token === "AMBIGUOUS_ORDER_BURST" ||
    token === "EXECUTION_FAILURE_BURST"
  ) {
    return "EXECUTION_REJECT_BURST";
  }
  if (token.includes("SAFETY") || token.includes("KILL_SWITCH")) {
    return "SAFETY_BLOCKED";
  }
  if (token.includes("MT5") && token.includes("REJECT")) return "MT5_REJECTED";
  if (token.includes("BROKER") && token.includes("REJECT")) {
    return "BROKER_REJECTED";
  }
  if (token.includes("OMS") && token.includes("REJECT")) return "OMS_REJECTED";
  if (token.includes("RISK_REJECT") || token === "RISK_BLOCK") {
    return "RISK_REJECTED";
  }
  return null;
}
