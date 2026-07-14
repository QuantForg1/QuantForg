import { asRecord, num, str } from "@/lib/desk";

export type AssetClass =
  | "forex"
  | "crypto"
  | "stocks"
  | "indices"
  | "commodities"
  | "etf"
  | "futures"
  | "cash"
  | "other";

const CRYPTO = /^(BTC|ETH|XRP|SOL|ADA|DOGE|LTC|BNB|DOT|AVAX|LINK|MATIC|USDT|USDC)/i;
const INDEX = /(US30|US500|NAS100|NASDAQ|SPX|DAX|FTSE|NI225|JP225|GER40|UK100|EU50)/i;
const COMMODITY = /(XAU|XAG|GOLD|SILVER|OIL|WTI|BRENT|COPPER|NATGAS|XTI|XBR)/i;
const ETF = /(ETF|SPY|QQQ|IWM|GLD|SLV|EEM|VTI)/i;
const FUTURES = /(FUT|CONT|\/F$|_F$)/i;
const FOREX = /^[A-Z]{6}$|^[A-Z]{3}[A-Z]{3}/;

export function classifySymbol(symbol: string): AssetClass {
  const s = symbol.toUpperCase().replace(/[^A-Z0-9]/g, "");
  if (!s) return "other";
  if (CRYPTO.test(s) || s.includes("USDT") || s.includes("BTC")) return "crypto";
  if (ETF.test(s)) return "etf";
  if (FUTURES.test(symbol.toUpperCase())) return "futures";
  if (INDEX.test(s)) return "indices";
  if (COMMODITY.test(s)) return "commodities";
  if (s.length <= 6 && FOREX.test(s) && !/\d/.test(s)) return "forex";
  if (s.length >= 1 && s.length <= 5 && /^[A-Z]+$/.test(s)) return "stocks";
  return "other";
}

export function sumPnlInWindow(
  deals: Record<string, unknown>[],
  windowMs: number,
  now = Date.now(),
): number {
  return deals.reduce((sum, d) => {
    const t = Date.parse(str(d.time, ""));
    if (!Number.isFinite(t) || now - t > windowMs) return sum;
    return sum + num(d.profit, 0);
  }, 0);
}

export function buildEquitySeries(
  deals: Record<string, unknown>[],
  seedEquity: number,
): { t: string; equity: number }[] {
  if (!deals.length) return [];
  const ordered = [...deals].sort(
    (a, b) => Date.parse(str(a.time, "0")) - Date.parse(str(b.time, "0")),
  );
  let equity = seedEquity;
  // Reconstruct by walking backwards from current equity using profit
  const profits = ordered.map((d) => num(d.profit, 0));
  const total = profits.reduce((s, p) => s + p, 0);
  equity = seedEquity - total;
  return ordered.map((d, i) => {
    equity += profits[i];
    const raw = str(d.time, String(i + 1));
    return {
      t: raw.includes("T") ? raw.slice(5, 16).replace("T", " ") : raw.slice(0, 16),
      equity,
    };
  });
}

export function sparkFromSeries(series: { equity: number }[], points = 12): number[] {
  if (!series.length) return [];
  if (series.length <= points) return series.map((s) => s.equity);
  const step = (series.length - 1) / (points - 1);
  return Array.from({ length: points }, (_, i) => {
    const idx = Math.round(i * step);
    return series[idx]?.equity ?? series[series.length - 1].equity;
  });
}

export function allocationFromPositions(
  positions: Record<string, unknown>[],
  cash: number,
): { name: string; value: number; classKey: AssetClass }[] {
  const map = new Map<AssetClass, number>();
  for (const p of positions) {
    const cls = classifySymbol(str(p.symbol, ""));
    const notional = Math.abs(num(p.volume, 0) * num(p.current_price ?? p.open_price, 0));
    const exposure = Number.isFinite(notional) && notional > 0 ? notional : Math.abs(num(p.profit, 0));
    map.set(cls, (map.get(cls) || 0) + (exposure || 0.01));
  }
  if (Number.isFinite(cash) && cash > 0) map.set("cash", (map.get("cash") || 0) + cash);

  const labels: Record<AssetClass, string> = {
    forex: "Forex",
    crypto: "Crypto",
    stocks: "Stocks",
    indices: "Indices",
    commodities: "Commodities",
    etf: "ETF",
    futures: "Futures",
    cash: "Cash",
    other: "Other",
  };

  return [...map.entries()]
    .filter(([, v]) => v > 0)
    .map(([classKey, value]) => ({ name: labels[classKey], value, classKey }))
    .sort((a, b) => b.value - a.value);
}

export function historicalVar95(pnls: number[]): number {
  if (pnls.length < 5) return NaN;
  const sorted = [...pnls].sort((a, b) => a - b);
  const idx = Math.max(0, Math.floor(0.05 * sorted.length));
  return Math.abs(Math.min(0, sorted[idx]));
}

export function durationLabel(openedAt: unknown): string {
  const t = Date.parse(str(openedAt, ""));
  if (!Number.isFinite(t)) return "—";
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 60) return `${mins}m`;
  const hrs = Math.round(mins / 60);
  if (hrs < 48) return `${hrs}h`;
  return `${Math.round(hrs / 24)}d`;
}

export function symbolSpread(sym: Record<string, unknown>): number {
  const bid = num(sym.bid);
  const ask = num(sym.ask);
  if (!Number.isFinite(bid) || !Number.isFinite(ask)) return NaN;
  return ask - bid;
}

export function marketBuckets(symbols: Record<string, unknown>[]) {
  const buckets: Record<string, number> = {
    Forex: 0,
    Crypto: 0,
    Indices: 0,
    Commodities: 0,
    Stocks: 0,
  };
  for (const s of symbols) {
    const cls = classifySymbol(str(s.code ?? s.symbol, ""));
    if (cls === "forex") buckets.Forex += 1;
    else if (cls === "crypto") buckets.Crypto += 1;
    else if (cls === "indices") buckets.Indices += 1;
    else if (cls === "commodities") buckets.Commodities += 1;
    else if (cls === "stocks") buckets.Stocks += 1;
  }
  return buckets;
}

export function topBySpread(symbols: Record<string, unknown>[], dir: "wide" | "tight", n = 5) {
  const scored = symbols
    .map((s) => ({ s, spread: symbolSpread(s) }))
    .filter((x) => Number.isFinite(x.spread));
  scored.sort((a, b) => (dir === "wide" ? b.spread - a.spread : a.spread - b.spread));
  return scored.slice(0, n).map((x) => asRecord(x.s));
}
