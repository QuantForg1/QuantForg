/**
 * Shared POST /strategy/evaluate contract.
 * Producer must match StrategyEvaluateRequest — extra fields are rejected.
 */

import { resolveTradingSymbol, TRADING_SYMBOL } from "../trading/gold-only";
import {
  assertStrategyEvaluateShape,
  mapStrategyEvaluateAliases,
} from "./strategy-evaluate-contract";

const BOOL_FLAGS = [
  "liquidity_sweep_bullish",
  "liquidity_sweep_bearish",
  "order_block_bullish",
  "order_block_bearish",
  "fvg_bullish",
  "fvg_bearish",
  "has_structure",
  "has_liquidity",
  "has_order_blocks",
  "has_fvgs",
  "check_risk",
  "market_open",
] as const;

const OPTIONAL_STRINGS = [
  "requested_lots",
  "stop_loss_distance",
  "entry_price",
  "equity",
  "balance",
  "last_price",
] as const;

export type StrategyEvaluatePayload = {
  request_id: string;
  symbol: string;
  timeframe: string;
  market_open: boolean;
  session: string;
  structure_bias: string;
  liquidity_sweep_bullish: boolean;
  liquidity_sweep_bearish: boolean;
  order_block_bullish: boolean;
  order_block_bearish: boolean;
  fvg_bullish: boolean;
  fvg_bearish: boolean;
  has_structure: boolean;
  has_liquidity: boolean;
  has_order_blocks: boolean;
  has_fvgs: boolean;
  analysis_notes: string[];
  check_risk: boolean;
  requested_lots?: string;
  stop_loss_distance?: string;
  entry_price?: string;
  equity?: string;
  balance?: string;
  tick_age_seconds?: number;
  candle_count?: number;
  last_price?: string;
};

function asBool(value: unknown, fallback: boolean): boolean {
  if (typeof value === "boolean") return value;
  return fallback;
}

function asTrimmed(value: unknown): string {
  return typeof value === "string" ? value.trim() : String(value ?? "").trim();
}

export function buildStrategyEvaluateRequest(
  input: Record<string, unknown> = {},
): StrategyEvaluatePayload {
  const src = mapStrategyEvaluateAliases(input);
  const requestId = asTrimmed(src.request_id) || `ui-eval-${Date.now()}`;
  const lots = asTrimmed(src.requested_lots);
  const notes = Array.isArray(src.analysis_notes)
    ? src.analysis_notes.map((n) => String(n)).slice(0, 20)
    : [];

  const body: StrategyEvaluatePayload = {
    request_id: requestId,
    symbol: resolveTradingSymbol(asTrimmed(src.symbol) || TRADING_SYMBOL),
    timeframe: asTrimmed(src.timeframe) || "m15",
    market_open: asBool(src.market_open, true),
    session: asTrimmed(src.session) || "unknown",
    structure_bias: asTrimmed(src.structure_bias) || "unknown",
    liquidity_sweep_bullish: asBool(src.liquidity_sweep_bullish, false),
    liquidity_sweep_bearish: asBool(src.liquidity_sweep_bearish, false),
    order_block_bullish: asBool(src.order_block_bullish, false),
    order_block_bearish: asBool(src.order_block_bearish, false),
    fvg_bullish: asBool(src.fvg_bullish, false),
    fvg_bearish: asBool(src.fvg_bearish, false),
    has_structure: asBool(src.has_structure, false),
    has_liquidity: asBool(src.has_liquidity, false),
    has_order_blocks: asBool(src.has_order_blocks, false),
    has_fvgs: asBool(src.has_fvgs, false),
    analysis_notes: notes,
    check_risk: asBool(src.check_risk, true),
  };

  if (lots) body.requested_lots = lots;
  for (const key of OPTIONAL_STRINGS) {
    if (key === "requested_lots") continue;
    const v = asTrimmed(src[key]);
    if (v) body[key] = v;
  }
  if (typeof src.tick_age_seconds === "number" && Number.isFinite(src.tick_age_seconds)) {
    body.tick_age_seconds = src.tick_age_seconds;
  }
  if (typeof src.candle_count === "number" && Number.isFinite(src.candle_count)) {
    body.candle_count = Math.trunc(src.candle_count);
  }

  assertStrategyEvaluateRequest(body);
  return body;
}

export function assertStrategyEvaluateRequest(body: Record<string, unknown>): void {
  assertStrategyEvaluateShape(body);
  for (const flag of BOOL_FLAGS) {
    if (flag in body && typeof body[flag] !== "boolean") {
      throw new Error(`strategy/evaluate '${flag}' must be boolean`);
    }
  }
}

export function isValidStrategyEvaluateRequest(body: Record<string, unknown>): boolean {
  try {
    assertStrategyEvaluateRequest(body);
    return true;
  } catch {
    return false;
  }
}
