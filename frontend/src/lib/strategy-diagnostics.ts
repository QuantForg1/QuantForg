/** Strategy Diagnostics — read-only NO_TRADE observation helpers. */

import { asList, asRecord, bool, num, str } from "@/lib/desk";

export type TrendBoard = {
  h4: string;
  h1: string;
  m15: string;
  m5: string;
  aligned: boolean | null;
  score: number | null;
};

export type QualityBoard = {
  score: number | null;
  required: number;
  difference: number | null;
  passed: boolean | null;
};

export type ConfluenceComponents = {
  smc: number | null;
  liquidity_sweep: number | null;
  bos: number | null;
  choch: number | null;
  order_block: number | null;
  fair_value_gap: number | null;
  trend_alignment: number | null;
  volume: number | null;
  news_filter: number | null;
};

export type ConfluenceBoard = {
  total: number | null;
  required: number;
  difference: number | null;
  passed: boolean | null;
  components: ConfluenceComponents;
};

export type RejectionBoard = {
  primary: string | null;
  secondary: string | null;
  tertiary: string | null;
  primaryLabel: string | null;
  secondaryLabel: string | null;
  tertiaryLabel: string | null;
  allLabels: string[];
  decisionReasons: string[];
};

export type DiagnosticCycle = {
  recordedAt: string;
  signalId: string;
  marketSession: string;
  sessionAllowed: boolean | null;
  cycleOutcome: string;
  decisionAction: string;
  executed: boolean;
  rejected: boolean;
  trend: TrendBoard;
  quality: QualityBoard;
  confluence: ConfluenceBoard;
  rejection: RejectionBoard;
};

export type DiagnosticsStats = {
  window: number;
  cyclesInWindow: number;
  signalsGenerated: number;
  signalsRejected: number;
  signalsExecuted: number;
  executionRatePct: number;
  averageQuality: number | null;
  averageConfluence: number | null;
  topRejectionReasons: Array<{
    code: string;
    label: string;
    count: number;
    sharePct: number;
  }>;
};

export type StrategyDiagnosticsModel = {
  advisoryOnly: boolean;
  thresholds: { requiredQuality: number; requiredConfluence: number };
  latest: DiagnosticCycle | null;
  cycles: DiagnosticCycle[];
  statistics: DiagnosticsStats;
  smartInsights: string[];
  empty: boolean;
};

function scoreOrNull(v: unknown): number | null {
  const n = num(v, NaN);
  return Number.isFinite(n) ? n : null;
}

function parseCycle(raw: unknown): DiagnosticCycle {
  const r = asRecord(raw);
  const trend = asRecord(r.trend);
  const quality = asRecord(r.quality);
  const confluence = asRecord(r.confluence);
  const components = asRecord(confluence.components);
  const rejection = asRecord(r.rejection);

  return {
    recordedAt: str(r.recorded_at, "—"),
    signalId: str(r.signal_id, "—"),
    marketSession: str(r.market_session, "—"),
    sessionAllowed:
      r.session_allowed == null ? null : bool(r.session_allowed),
    cycleOutcome: str(r.cycle_outcome, "—"),
    decisionAction: str(r.decision_action, "—"),
    executed: bool(r.executed),
    rejected: bool(r.rejected),
    trend: {
      h4: str(trend.h4, "—"),
      h1: str(trend.h1, "—"),
      m15: str(trend.m15, "—"),
      m5: str(trend.m5, "—"),
      aligned: trend.aligned == null ? null : bool(trend.aligned),
      score: scoreOrNull(trend.score),
    },
    quality: {
      score: scoreOrNull(quality.score),
      required: num(quality.required, 80),
      difference: scoreOrNull(quality.difference),
      passed: quality.passed == null ? null : bool(quality.passed),
    },
    confluence: {
      total: scoreOrNull(confluence.total),
      required: num(confluence.required, 80),
      difference: scoreOrNull(confluence.difference),
      passed: confluence.passed == null ? null : bool(confluence.passed),
      components: {
        smc: scoreOrNull(components.smc),
        liquidity_sweep: scoreOrNull(components.liquidity_sweep),
        bos: scoreOrNull(components.bos),
        choch: scoreOrNull(components.choch),
        order_block: scoreOrNull(components.order_block),
        fair_value_gap: scoreOrNull(components.fair_value_gap),
        trend_alignment: scoreOrNull(components.trend_alignment),
        volume: scoreOrNull(components.volume),
        news_filter: scoreOrNull(components.news_filter),
      },
    },
    rejection: {
      primary: str(rejection.primary, "") || null,
      secondary: str(rejection.secondary, "") || null,
      tertiary: str(rejection.tertiary, "") || null,
      primaryLabel: str(rejection.primary_label, "") || null,
      secondaryLabel: str(rejection.secondary_label, "") || null,
      tertiaryLabel: str(rejection.tertiary_label, "") || null,
      allLabels: asList(rejection.all_labels).map(String),
      decisionReasons: asList(rejection.decision_reasons).map(String),
    },
  };
}

export function buildStrategyDiagnosticsModel(
  payload: unknown,
): StrategyDiagnosticsModel {
  const root = asRecord(payload);
  const thresholds = asRecord(root.thresholds);
  const statistics = asRecord(root.statistics);
  const cycles = asList(root.cycles).map(parseCycle);
  const latest = root.latest != null ? parseCycle(root.latest) : cycles[0] ?? null;
  const top = asList(statistics.top_rejection_reasons).map((item) => {
    const r = asRecord(item);
    return {
      code: str(r.code, "—"),
      label: str(r.label, "—"),
      count: num(r.count, 0),
      sharePct: num(r.share_pct, 0),
    };
  });

  return {
    advisoryOnly: root.advisory_only == null ? true : bool(root.advisory_only),
    thresholds: {
      requiredQuality: num(thresholds.required_quality, 80),
      requiredConfluence: num(thresholds.required_confluence, 80),
    },
    latest,
    cycles,
    statistics: {
      window: num(statistics.window, 100),
      cyclesInWindow: num(statistics.cycles_in_window, cycles.length),
      signalsGenerated: num(statistics.signals_generated, 0),
      signalsRejected: num(statistics.signals_rejected, 0),
      signalsExecuted: num(statistics.signals_executed, 0),
      executionRatePct: num(statistics.execution_rate_pct, 0),
      averageQuality: scoreOrNull(statistics.average_quality),
      averageConfluence: scoreOrNull(statistics.average_confluence),
      topRejectionReasons: top,
    },
    smartInsights: asList(root.smart_insights).map(String),
    empty: cycles.length === 0,
  };
}

export function fmtScore(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return String(Math.round(v));
}

export function fmtDiff(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const n = Math.round(v);
  return n > 0 ? `+${n}` : String(n);
}
