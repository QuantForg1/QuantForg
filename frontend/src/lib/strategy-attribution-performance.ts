/**
 * Pure view-model helpers for the LIVE Strategy Performance Dashboard.
 * Server remains the source of truth for financial metrics — no recalc.
 */

export type ClassificationTone = "ok" | "warn" | "bad" | "neutral" | "accent";

export interface PeriodBucketView {
  label: string;
  brokerLogin: number | null;
  n: number;
  attributed: number;
  unattributed: number;
  attributionCoveragePct: number | null;
  incompleteCostRecords: number;
  realizedNetPnl: number | null;
  unrealizedPnl: null;
  winRate: number | null;
  profitFactor: number | null;
  expectancy: number | null;
  avgWin: number | null;
  avgLoss: number | null;
  maxDrawdown: number | null;
  maxConsecutiveLosses: number | null;
  classification: string;
  buy: SideView;
  sell: SideView;
  reversalLikeCloses: number;
  dataQualityNote: string;
}

export interface SideView {
  n: number;
  net: number | null;
  winRate: number | null;
  profitFactor: number | null;
  expectancy: number | null;
  avgWin: number | null;
  avgLoss: number | null;
  maxDrawdown: number | null;
  classification: string;
}

export interface StrategyCardView {
  strategyId: string | null;
  strategyName: string;
  closedTrades: number;
  netPnl: number | null;
  winRate: number | null;
  profitFactor: number | null;
  expectancy: number | null;
  avgWin: number | null;
  avgLoss: number | null;
  maxDrawdown: number | null;
  buyN: number;
  sellN: number;
  buyNet: number | null;
  sellNet: number | null;
  attributionConfidence: string;
  sampleSize: number;
  classification: string;
  isUnattributed: boolean;
  isInsufficientData: boolean;
}

export interface StrategyPerformanceDashboardModel {
  asOf: string | null;
  brokerLogin: number | null;
  reportingPeriod: string;
  instrument: string;
  accountNote: string;
  overview: PeriodBucketView;
  periods: PeriodBucketView[];
  scorecards: StrategyCardView[];
  unattributed: StrategyCardView | null;
  capitalProtection: {
    buyActiveAnchors: number | null;
    sellActiveAnchors: number | null;
    buyTrusted: boolean | null;
    sellTrusted: boolean | null;
    reversalCloses: number | null;
    buyNote: string;
    sellNote: string;
    historicalBlocksUnavailable: true;
  };
  m1: {
    microEnabled: boolean | null;
    liveSubmit: boolean | null;
    liveSubmitLabel: string;
    status: string;
    recommendation: string;
    displayRule: string;
  };
  advisoryOnly: boolean;
  mutatesEngines: boolean;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function num(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function str(value: unknown, fallback = "—"): string {
  if (value == null || value === "") return fallback;
  return String(value);
}

function boolOrNull(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  return null;
}

export function formatMoney(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

export function formatPct(value: number | null | undefined, asRatio = true): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const pct = asRatio ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
}

export function formatPf(value: number | null | undefined): string {
  if (value == null) return "—";
  if (!Number.isFinite(value)) return "∞";
  return value.toFixed(2);
}

export function formatExpectancy(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return value.toFixed(4);
}

export function classificationTone(label: string): ClassificationTone {
  const t = label.toLowerCase();
  if (t.includes("positive expectancy demonstrated") || t.includes("demonstrated positive")) {
    return "ok";
  }
  if (t.includes("negative")) return "bad";
  if (t.includes("promising")) return "accent";
  if (t.includes("insufficient attribution") || t.includes("insufficient data")) {
    return "warn";
  }
  return "neutral";
}

export function pnlTone(value: number | null | undefined): ClassificationTone {
  if (value == null) return "neutral";
  if (value > 0) return "ok";
  if (value < 0) return "bad";
  return "neutral";
}

function mapSide(raw: Record<string, unknown>): SideView {
  return {
    n: num(raw.n) ?? 0,
    net: num(raw.net),
    winRate: num(raw.win_rate),
    profitFactor: num(raw.profit_factor),
    expectancy: num(raw.expectancy),
    avgWin: num(raw.avg_win),
    avgLoss: num(raw.avg_loss),
    maxDrawdown: num(raw.max_drawdown),
    classification: str(raw.classification, "Insufficient data"),
  };
}

function mapPeriod(raw: Record<string, unknown>): PeriodBucketView {
  const buy = asRecord(raw.buy);
  const sell = asRecord(raw.sell);
  const dq = asRecord(raw.data_quality);
  return {
    label: str(raw.label, "period"),
    brokerLogin: num(raw.broker_login),
    n: num(raw.n) ?? 0,
    attributed: num(raw.attributed) ?? 0,
    unattributed: num(raw.unattributed) ?? 0,
    attributionCoveragePct: num(raw.attribution_coverage_pct),
    incompleteCostRecords: num(raw.incomplete_cost_records) ?? 0,
    realizedNetPnl: num(raw.realized_net_pnl ?? raw.net_profit),
    unrealizedPnl: null,
    winRate: num(raw.win_rate),
    profitFactor: num(raw.profit_factor),
    expectancy: num(raw.expectancy),
    avgWin: num(raw.avg_win),
    avgLoss: num(raw.avg_loss),
    maxDrawdown: num(raw.max_drawdown),
    maxConsecutiveLosses: num(raw.max_consecutive_losses),
    classification: str(raw.classification, "Insufficient data"),
    buy: mapSide(buy),
    sell: mapSide(sell),
    reversalLikeCloses: num(raw.reversal_like_closes) ?? 0,
    dataQualityNote: str(dq.note, ""),
  };
}

function mapCard(raw: Record<string, unknown>): StrategyCardView {
  const strategyId =
    raw.strategy_id == null || raw.strategy_id === ""
      ? null
      : String(raw.strategy_id);
  const closed = num(raw.closed_trades) ?? 0;
  const classification = str(raw.classification, "Insufficient data");
  return {
    strategyId,
    strategyName: str(raw.strategy_name, strategyId ?? "Unattributed"),
    closedTrades: closed,
    netPnl: num(raw.net_pnl),
    winRate: num(raw.win_rate),
    profitFactor: num(raw.profit_factor),
    expectancy: num(raw.expectancy),
    avgWin: num(raw.avg_win),
    avgLoss: num(raw.avg_loss),
    maxDrawdown: num(raw.max_drawdown),
    buyN: num(raw.buy_n) ?? 0,
    sellN: num(raw.sell_n) ?? 0,
    buyNet: num(raw.buy_net),
    sellNet: num(raw.sell_net),
    attributionConfidence: str(raw.attribution_confidence, "unknown"),
    sampleSize: num(raw.sample_size) ?? closed,
    classification,
    isUnattributed: strategyId == null,
    isInsufficientData:
      closed === 0 || classification.toLowerCase().includes("insufficient data"),
  };
}

export function buildStrategyPerformanceDashboardModel(
  payload: Record<string, unknown>,
): StrategyPerformanceDashboardModel {
  const overviewSource =
    Object.keys(asRecord(payload.overview)).length > 0
      ? asRecord(payload.overview)
      : asRecord(payload.post_pr182);
  const overview = mapPeriod(overviewSource);

  const periodsRaw = asRecord(payload.periods);
  const periods = Object.keys(periodsRaw)
    .sort()
    .map((key) => mapPeriod({ ...asRecord(periodsRaw[key]), label: key }));

  const cardsRaw = Array.isArray(payload.five_pack_scorecards_post_pr182)
    ? payload.five_pack_scorecards_post_pr182
    : [];
  const allCards = cardsRaw.map((c) => mapCard(asRecord(c)));
  const scorecards = allCards.filter((c) => !c.isUnattributed);
  const unattributed = allCards.find((c) => c.isUnattributed) ?? null;

  const protection = asRecord(payload.capital_protection);
  const buyCascade = asRecord(protection.buy_cascade);
  const sellCascade = asRecord(protection.sell_cascade);
  const reversal = asRecord(protection.reversal);
  const m1 = asRecord(payload.m1);

  return {
    asOf: str(payload.as_of, "") || null,
    brokerLogin: num(payload.broker_login),
    reportingPeriod: str(payload.reporting_period, "post_pr182"),
    instrument: str(payload.instrument, "XAUUSD"),
    accountNote: str(payload.account_12260878_note, ""),
    overview,
    periods,
    scorecards,
    unattributed,
    capitalProtection: {
      buyActiveAnchors: num(buyCascade.active_anchors),
      sellActiveAnchors: num(sellCascade.active_anchors),
      buyTrusted: boolOrNull(buyCascade.store_trusted),
      sellTrusted: boolOrNull(sellCascade.store_trusted),
      reversalCloses: num(reversal.broker_confirmed_reversal_like_closes),
      buyNote: str(buyCascade.note, ""),
      sellNote: str(sellCascade.note, ""),
      historicalBlocksUnavailable: true,
    },
    m1: {
      microEnabled: boolOrNull(m1.m1_micro_enabled),
      liveSubmit: boolOrNull(m1.m1_live_submit),
      liveSubmitLabel: str(m1.m1_live_oms_submission, "OFF"),
      status: str(m1.status, "UNKNOWN"),
      recommendation: str(m1.recommendation, ""),
      displayRule: str(
        m1.display_rule,
        "M1 signal counts are not completed trades and are not profitability.",
      ),
    },
    advisoryOnly: payload.advisory_only !== false,
    mutatesEngines: payload.mutates_engines === true,
  };
}

export function scorecardChartRows(
  cards: StrategyCardView[],
): Array<Record<string, string | number>> {
  return cards.map((c) => ({
    label: c.strategyId ?? "unknown",
    value: c.isInsufficientData ? 0 : (c.netPnl ?? 0),
    sample: c.sampleSize,
  }));
}
