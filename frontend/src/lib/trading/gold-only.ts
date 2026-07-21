/**
 * XAUUSD-only trading mode.
 *
 * QuantForg is a single-instrument gold desk. Multi-asset mode is removed.
 */

export const GOLD_SYMBOL = "XAUUSD";

/** Always false — platform mandate. */
export const MULTI_SYMBOL_ENABLED = false;

/** Active default / forced trading symbol. */
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
  return isGoldSymbol(code);
}

/** Resolve any input to XAUUSD. */
/** Resolve any input to XAUUSD. */
export function resolveTradingSymbol(code?: string | null): string {
  void code;
  return GOLD_SYMBOL;
}

/**
 * Map a user search string to an MT5 `q` param.
 * Non-gold queries return null → callers should show an empty result set.
 */
export function goldOnlySearchQuery(q?: string): string | null {
  const raw = (q || "").trim().toUpperCase();
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
