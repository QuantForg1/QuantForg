/**
 * Trading symbol policy for the QuantForg frontend.
 *
 * Terminal watchlist/charts may list broker symbols for manual viewing.
 * Autonomous execution is GOLD ONLY (backend ``gold_only_mode`` is
 * authoritative). Default focus remains Weltrade gold CFD ``XAUUSD_i``.
 * Order routing still goes through existing backend Risk/OMS gates — this file
 * only controls client display / API path encoding.
 */

export const GOLD_SYMBOL = "XAUUSD";

/** Weltrade / institutional gold CFD — exact broker catalogue spelling. */
export const WELTRADE_XAUUSD = "XAUUSD_i";

/** Multi-asset Terminal watchlist, charts, and tickets are enabled. */
export const MULTI_SYMBOL_ENABLED = true;

/** Default desk focus when no symbol is selected. */
export const TRADING_SYMBOL = MULTI_SYMBOL_ENABLED ? WELTRADE_XAUUSD : GOLD_SYMBOL;

const GOLD_ALIASES = new Set([
  "XAUUSD",
  "GOLD",
  "XAUUSDM",
  "XAUUSD.",
  "XAUUSD.A",
  "XAUUSD_I",
]);

/** Desk aliases → exact Weltrade broker symbols (preserve lowercase ``_i``). */
const DESK_TO_BROKER: Record<string, string> = {
  XAUUSD: WELTRADE_XAUUSD,
  GOLD: WELTRADE_XAUUSD,
  XAUUSDM: WELTRADE_XAUUSD,
  "XAUUSD.": WELTRADE_XAUUSD,
  "XAUUSD.A": WELTRADE_XAUUSD,
  XAUUSD_I: WELTRADE_XAUUSD,
};

export function normalizeSymbolCode(code: string): string {
  return code.trim().toUpperCase().replace(/[^A-Z0-9.]/g, "");
}

export function isGoldSymbol(code: string): boolean {
  const u = normalizeSymbolCode(code);
  if (!u) return false;
  if (GOLD_ALIASES.has(u) || u === GOLD_SYMBOL || u === "XAUUSD_I") return true;
  return u.includes("XAUUSD") || (u.includes("XAU") && u.includes("USD"));
}

export function isAllowedTradingSymbol(code: string): boolean {
  const u = normalizeSymbolCode(code);
  if (!u) return false;
  if (MULTI_SYMBOL_ENABLED) return true;
  return isGoldSymbol(u);
}

/**
 * Resolve a user/URL symbol for API paths and Terminal state.
 * ``XAUUSD`` → ``XAUUSD_i``; never send uppercase ``XAUUSD_I`` to the gateway.
 */
export function resolveTradingSymbol(code?: string | null): string {
  const raw = (code || "").trim();
  if (!raw) return TRADING_SYMBOL;

  // Preserve institutional suffix as broker lowercase ``_i``.
  const inst = raw.match(/^([A-Za-z0-9.]+)[_ ]([iI])$/);
  if (inst) {
    const base = inst[1].toUpperCase().replace(/[^A-Z0-9.]/g, "");
    return `${base}_i`;
  }

  const n = normalizeSymbolCode(raw);
  if (!MULTI_SYMBOL_ENABLED) return GOLD_SYMBOL;
  if (DESK_TO_BROKER[n]) return DESK_TO_BROKER[n];
  // Generic Weltrade institutional uppercase form → catalogue ``_i``.
  if (n.endsWith("_I") && n.length > 2) {
    return `${n.slice(0, -2)}_i`;
  }
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
    if (!raw) return "";
    // Prefer broker spelling for gold searches so catalogue match succeeds.
    if (
      GOLD_SYMBOL.includes(raw) ||
      raw.includes("XAU") ||
      raw.includes("GOLD") ||
      isGoldSymbol(raw)
    ) {
      return WELTRADE_XAUUSD;
    }
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

export const DEFAULT_WATCHLIST_SYMBOLS = [TRADING_SYMBOL] as const;

/** MT5 XAUUSD contract specs used by client-side sizing / display. */
export const XAUUSD_SPECS = {
  symbol: WELTRADE_XAUUSD,
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
