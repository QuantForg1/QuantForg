/**
 * Gold-only trading mode.
 *
 * QuantForg is constrained to XAUUSD unless multi-symbol is explicitly enabled
 * via NEXT_PUBLIC_MULTI_SYMBOL=true (future). Architecture stays multi-symbol-ready;
 * this module is the single switch.
 */

export const GOLD_SYMBOL = "XAUUSD";

/** Future escape hatch — leave false for Gold-only terminal. */
export const MULTI_SYMBOL_ENABLED =
  process.env.NEXT_PUBLIC_MULTI_SYMBOL === "true";

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
  if (MULTI_SYMBOL_ENABLED) return Boolean(code.trim());
  return isGoldSymbol(code);
}

/** Resolve any input to the symbol the terminal may trade. */
export function resolveTradingSymbol(code?: string | null): string {
  if (MULTI_SYMBOL_ENABLED) {
    const s = (code || "").trim().toUpperCase();
    return s || GOLD_SYMBOL;
  }
  return GOLD_SYMBOL;
}

/**
 * Map a user search string to an MT5 `q` param.
 * Non-gold queries return null → callers should show an empty result set.
 */
export function goldOnlySearchQuery(q?: string): string | null {
  if (MULTI_SYMBOL_ENABLED) return (q || "").trim();
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
  if (MULTI_SYMBOL_ENABLED) return items;
  return items.filter((item) =>
    isGoldSymbol(String(item.code ?? item.symbol ?? "")),
  );
}

export const DEFAULT_WATCHLIST_SYMBOLS = [GOLD_SYMBOL] as const;
