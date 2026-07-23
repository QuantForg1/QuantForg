/** Threshold Performance Analysis — offline research helpers + exports. */

import { asList, asRecord, bool, num, str } from "@/lib/desk";
import {
  downloadBytes,
  downloadJson,
} from "@/lib/production-acceptance-test";

export type TpaCell = {
  qualityGate: number;
  confluenceGate: number;
  isBaseline: boolean;
  totalSignals: number;
  executedTrades: number;
  rejectedTrades: number;
  winRate: number | null;
  lossRate: number | null;
  averageRr: number | null;
  averageHoldingTimeSec: number | null;
  profitFactor: number | null;
  grossProfit: number | null;
  grossLoss: number | null;
  netProfit: number | null;
  expectancy: number | null;
  maximumDrawdownPct: number | null;
  recoveryFactor: number | null;
  sharpeRatio: number | null;
  averageSpread: number | null;
  averageSlippage: number | null;
};

export type TpaModel = {
  empty: boolean;
  generatedAt: string;
  evaluations: number;
  recommendationSummary: string;
  recommendationAction: string;
  matrix: TpaCell[];
  rankings: Record<string, Array<{ label: string; value: string }>>;
  heatmap: Array<{
    qualityGate: number;
    confluenceGate: number;
    profitFactor: number | null;
    winRate: number | null;
    expectancy: number | null;
    drawdown: number | null;
  }>;
  raw: Record<string, unknown>;
};

function n(v: unknown): number | null {
  const x = num(v, NaN);
  return Number.isFinite(x) ? x : null;
}

function fmt(v: number | null | undefined, digits = 2): string {
  if (v == null || !Number.isFinite(v)) return "—";
  return v.toFixed(digits);
}

function parseCell(raw: unknown): TpaCell {
  const r = asRecord(raw);
  return {
    qualityGate: num(r.quality_gate, 0),
    confluenceGate: num(r.confluence_gate, 0),
    isBaseline: bool(r.is_baseline),
    totalSignals: num(r.total_signals, 0),
    executedTrades: num(r.executed_trades, 0),
    rejectedTrades: num(r.rejected_trades, 0),
    winRate: n(r.win_rate),
    lossRate: n(r.loss_rate),
    averageRr: n(r.average_rr),
    averageHoldingTimeSec: n(r.average_holding_time_sec),
    profitFactor: n(r.profit_factor),
    grossProfit: n(r.gross_profit),
    grossLoss: n(r.gross_loss),
    netProfit: n(r.net_profit),
    expectancy: n(r.expectancy),
    maximumDrawdownPct: n(r.maximum_drawdown_pct),
    recoveryFactor: n(r.recovery_factor),
    sharpeRatio: n(r.sharpe_ratio),
    averageSpread: n(r.average_spread),
    averageSlippage: n(r.average_slippage),
  };
}

export function buildTpaModel(payload: unknown): TpaModel {
  const root = asRecord(payload);
  if (str(root.status) === "empty" || !asList(root.matrix).length) {
    return {
      empty: true,
      generatedAt: str(root.generated_at, "—"),
      evaluations: 0,
      recommendationSummary: "Keep production thresholds unchanged.",
      recommendationAction: "keep_production_thresholds_unchanged",
      matrix: [],
      rankings: {},
      heatmap: [],
      raw: root,
    };
  }
  const rec = asRecord(root.recommendation);
  const ranks = asRecord(root.rankings);
  const rankingOut: TpaModel["rankings"] = {};
  for (const [key, label] of [
    ["best_net_profit", "Best Net Profit"],
    ["best_profit_factor", "Best Profit Factor"],
    ["lowest_drawdown", "Lowest Drawdown"],
    ["best_expectancy", "Best Expectancy"],
    ["best_risk_adjusted_return", "Best Risk Adjusted Return"],
  ] as const) {
    rankingOut[label] = asList(ranks[key]).map((item) => {
      const r = asRecord(item);
      return {
        label: `Q${r.quality_gate}/C${r.confluence_gate}`,
        value: fmt(n(r.value), 4),
      };
    });
  }
  const heat = asList(asRecord(root.heatmap).cells).map((item) => {
    const r = asRecord(item);
    return {
      qualityGate: num(r.quality_gate, 0),
      confluenceGate: num(r.confluence_gate, 0),
      profitFactor: n(r.profit_factor),
      winRate: n(r.win_rate),
      expectancy: n(r.expectancy),
      drawdown: n(r.drawdown),
    };
  });

  return {
    empty: false,
    generatedAt: str(root.generated_at, "—"),
    evaluations: num(root.evaluations, 0),
    recommendationSummary: str(
      rec.summary,
      "Keep production thresholds unchanged.",
    ),
    recommendationAction: str(rec.action, "keep_production_thresholds_unchanged"),
    matrix: asList(root.matrix).map(parseCell),
    rankings: rankingOut,
    heatmap: heat,
    raw: root,
  };
}

export function matrixToCsv(matrix: TpaCell[]): string {
  const headers = [
    "quality_gate",
    "confluence_gate",
    "is_baseline",
    "total_signals",
    "executed_trades",
    "rejected_trades",
    "win_rate",
    "loss_rate",
    "average_rr",
    "average_holding_time_sec",
    "profit_factor",
    "gross_profit",
    "gross_loss",
    "net_profit",
    "expectancy",
    "maximum_drawdown_pct",
    "recovery_factor",
    "sharpe_ratio",
    "average_spread",
    "average_slippage",
  ];
  const lines = [headers.join(",")];
  for (const m of matrix) {
    const row = [
      m.qualityGate,
      m.confluenceGate,
      m.isBaseline,
      m.totalSignals,
      m.executedTrades,
      m.rejectedTrades,
      m.winRate,
      m.lossRate,
      m.averageRr,
      m.averageHoldingTimeSec,
      m.profitFactor,
      m.grossProfit,
      m.grossLoss,
      m.netProfit,
      m.expectancy,
      m.maximumDrawdownPct,
      m.recoveryFactor,
      m.sharpeRatio,
      m.averageSpread,
      m.averageSlippage,
    ];
    lines.push(row.map((v) => (v == null ? "" : String(v))).join(","));
  }
  return lines.join("\n");
}

export function buildTpaPdfBytes(model: TpaModel): Uint8Array {
  const lines: string[] = [
    "Threshold Performance Analysis",
    `Generated: ${model.generatedAt}`,
    `Evaluations: ${model.evaluations}`,
    `Recommendation: ${model.recommendationSummary.slice(0, 100)}`,
    "",
    "Matrix (Q/C Net PF WR DD):",
  ];
  for (const m of model.matrix.slice(0, 40)) {
    lines.push(
      `Q${m.qualityGate}/C${m.confluenceGate} net=${fmt(m.netProfit)} pf=${fmt(m.profitFactor)} wr=${fmt(m.winRate, 3)} dd=${fmt(m.maximumDrawdownPct)}`,
    );
  }
  lines.push("", "Offline research only. Live thresholds unchanged.");

  const escapePdf = (s: string) =>
    s.replace(/\\/g, "\\\\").replace(/\(/g, "\\(").replace(/\)/g, "\\)");

  let y = 780;
  const contentParts: string[] = ["BT", "/F1 9 Tf", "11 TL"];
  for (const line of lines) {
    contentParts.push(`1 0 0 1 36 ${y} Tm (${escapePdf(line.slice(0, 110))}) Tj`);
    y -= 11;
    if (y < 40) break;
  }
  contentParts.push("ET");
  const stream = contentParts.join("\n");
  const objects: string[] = [
    "1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj",
    "2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj",
    "3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj",
    `4 0 obj<< /Length ${stream.length} >>stream\n${stream}\nendstream endobj`,
    "5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj",
  ];
  let pdf = "%PDF-1.4\n";
  const offsets: number[] = [0];
  for (const obj of objects) {
    offsets.push(pdf.length);
    pdf += obj + "\n";
  }
  const xrefStart = pdf.length;
  pdf += `xref\n0 ${objects.length + 1}\n`;
  pdf += "0000000000 65535 f \n";
  for (let i = 1; i < offsets.length; i++) {
    pdf += `${String(offsets[i]).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer<< /Size ${objects.length + 1} /Root 1 0 R >>\n`;
  pdf += `startxref\n${xrefStart}\n%%EOF`;
  return new TextEncoder().encode(pdf);
}

export function exportTpaJson(model: TpaModel): void {
  downloadJson(`threshold-performance-${Date.now()}.json`, model.raw);
}

export function exportTpaCsv(model: TpaModel): void {
  const csv = matrixToCsv(model.matrix);
  downloadBytes(
    `threshold-performance-${Date.now()}.csv`,
    new TextEncoder().encode(csv),
    "text/csv",
  );
}

export function exportTpaPdf(model: TpaModel): void {
  downloadBytes(
    `threshold-performance-${Date.now()}.pdf`,
    buildTpaPdfBytes(model),
    "application/pdf",
  );
}

export { fmt as fmtTpa };
