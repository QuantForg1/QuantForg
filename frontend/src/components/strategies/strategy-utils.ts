import { asRecord, str } from "@/lib/desk";

export function isFlatPrimitiveParams(obj: Record<string, unknown>): boolean {
  const entries = Object.entries(obj);
  if (entries.length === 0) return false;
  return entries.every(([, v]) => {
    if (v === null) return true;
    const t = typeof v;
    return t === "string" || t === "number" || t === "boolean";
  });
}

export function mergedParamsFromJson(
  paramsJson: string,
  defaultParams: Record<string, unknown> | undefined,
): Record<string, unknown> {
  const defaults = defaultParams ?? {};
  try {
    const parsed = JSON.parse(paramsJson.trim() || "{}") as Record<string, unknown>;
    if (Object.keys(parsed).length === 0) return { ...defaults };
    return { ...defaults, ...parsed };
  } catch {
    return { ...defaults };
  }
}

export function serializeParams(obj: Record<string, unknown>): string {
  return JSON.stringify(obj, null, 2);
}

export type PerformanceField = { label: string; value: string };

export function extractBacktestPerformance(
  lastResult: Record<string, unknown> | null,
  portfolioData: unknown,
): PerformanceField[] {
  const out: PerformanceField[] = [];
  const sources = [
    asRecord(lastResult),
    asRecord(lastResult?.backtest),
    asRecord(lastResult?.performance),
    asRecord(portfolioData),
    asRecord(asRecord(portfolioData).performance),
  ];

  const keys: { key: string; label: string; pct?: boolean }[] = [
    { key: "win_rate", label: "Win rate", pct: true },
    { key: "total_trades", label: "Total trades" },
    { key: "profit_factor", label: "Profit factor" },
    { key: "sharpe", label: "Sharpe" },
    { key: "max_drawdown", label: "Max drawdown", pct: true },
    { key: "net_pnl", label: "Net PnL" },
  ];

  for (const { key, label, pct } of keys) {
    let raw: unknown;
    for (const src of sources) {
      if (src[key] !== undefined && src[key] !== null && src[key] !== "") {
        raw = src[key];
        break;
      }
    }
    if (raw === undefined) continue;
    const n = typeof raw === "number" ? raw : Number(raw);
    if (pct && Number.isFinite(n)) {
      out.push({ label, value: `${(n <= 1 ? n * 100 : n).toFixed(1)}%` });
    } else if (Number.isFinite(n)) {
      out.push({ label, value: String(n) });
    } else {
      out.push({ label, value: str(raw) });
    }
  }
  return out;
}

export function buildStrategyRules(
  description: string,
  symbol: string,
  timeframe: string,
  maxTrades: string,
  dailyLoss: string,
  maxExposure: string,
): string[] {
  const rules: string[] = [];
  const desc = description.trim();
  if (desc) rules.push(desc);
  rules.push(
    `Trade only ${symbol} (gold desk) — universe matches Risk Center policy.`,
    `Evaluate on ${timeframe} bars from MT5 when connected; no synthetic prices.`,
    `Session limits: max ${maxTrades} concurrent intentions per evaluate cycle.`,
    `Daily loss ceiling ${dailyLoss}% and max exposure ${maxExposure}% flow through engine limits.`,
    `Live execution requires Risk Center allowance, OMS gates, and owned broker session.`,
    `Parameters are advisory until validate + risk checks pass — never bypass safeguards.`,
  );
  return rules;
}
