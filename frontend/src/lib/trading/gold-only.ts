/**
 * Trading symbol policy for the QuantForg frontend.
 *
 * Production supports multi-asset (LIVE MT5 universe). Default focus remains XAUUSD.
 * Order routing still goes through existing backend Risk/OMS gates — this file only
 * controls client display / API path encoding.
 */

export const GOLD_SYMBOL = "XAUUSD";

/** Multi-asset Terminal watchlist, charts, and tickets are enabled. */
export const MULTI_SYMBOL_ENABLED = true;

/** Default desk focus when no symbol is selected. */
export const TRADING_SYMBOL = GOLD_SYMBOL;

const GOLD_ALIASES = new Set(["XAUUSD", "GOLD", "XAUUSDM", "XAUUSD.", "XAUUSD.a"]);

export function normalizeSymbolCode(code: string): string {
  return code.trim().toUpperCase().replace(/[^A-Z0-9.]/g, "");
}

export function isGoldSymbol(code: string): boolean {
  const u = normalizeSymbolCode(code);
  if (!u) return false;
  if (GOLD_ALIASES.has(u) || u === GOLD_SYMBOL) return true;
  return u.includes("XAUUSD") || (u.includes("XAU") && u.includes("USD"));
}

export function isAllowedTradingSymbol(code: string): boolean {
  const u = normalizeSymbolCode(code);
  if (!u) return false;
  if (MULTI_SYMBOL_ENABLED) return true;
  return isGoldSymbol(u);
}

/** Resolve a user/URL symbol for API paths and Terminal state. */
export function resolveTradingSymbol(code?: string | null): string {
  const n = normalizeSymbolCode(code || "");
  if (!n) return GOLD_SYMBOL;
  if (!MULTI_SYMBOL_ENABLED) return GOLD_SYMBOL;
  return n;
}

/**
 * Map a user search string to an MT5 `q` param.
 * Multi-asset: empty string lists the broker catalogue.
 * Gold-only: non-gold queries return null → empty result set.
 */
export function goldOnlySearchQuery(q?: string): string | null {
  const raw = (q || "").trim().toUpperCase();
  if (MULTI_SYMBOL_ENABLED) {
    return raw;
  }
  if (!raw) return GOLD_SYMBOL;
  if (
    GOLD_SYMBOL.includes(raw) ||
    raw.includes("XAU") ||
    raw.includes("GOLD") ||
    isGoldSymbol(raw)
  ) {
    return GOLD_SYMBOL;
  }
  return null;
}

export function filterTradingSymbolRecords<T extends Record<string, unknown>>(
  items: T[],
): T[] {
  if (MULTI_SYMBOL_ENABLED) return items;
  return items.filter((item) =>
    isGoldSymbol(String(item.code ?? item.symbol ?? "")),
  );
}

export const DEFAULT_WATCHLIST_SYMBOLS = [GOLD_SYMBOL] as const;

/** MT5 XAUUSD contract specs used by client-side sizing / display. */
export const XAUUSD_SPECS = {
  symbol: GOLD_SYMBOL,
  digits: 2,
  point: 0.01,
  tickSize: 0.01,
  tickValue: 1,
  contractSize: 100,
  volumeMin: 0.01,
  volumeMax: 10,
  volumeStep: 0.01,
  maxSpread: 2,
  maxLeverage: 1000,
} as const;
