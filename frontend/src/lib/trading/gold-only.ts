/**
 * Trading symbol policy for the QuantForg frontend.
 *
 * Backend ``EXECUTION_UNIVERSE_MODE`` is authoritative. This file does not
 * restore a gold-only production lock. XAUUSD_i remains supported; other
 * broker-discovered symbols are allowed in the desk UI.
 * Order routing still goes through existing backend Risk/OMS gates.
 */

export const GOLD_SYMBOL = "XAUUSD";

/** Weltrade / institutional gold CFD — exact broker catalogue spelling. */
export const WELTRADE_XAUUSD = "XAUUSD_i";

/** Canonical autonomous execution symbol. */
export const AUTONOMOUS_SYMBOL = WELTRADE_XAUUSD;

/** Operator-facing display. */
export const AUTONOMOUS_DISPLAY = "XAUUSD (Gold)";

/** Compact non-editable badge. */
export const AUTONOMOUS_BADGE = "XAUUSD · GOLD";

/**
 * Broker-discovered symbols are allowed in the desk UI.
 * Autonomous execution still uses backend Risk / Safety / OMS gates.
 */
export const MULTI_SYMBOL_ENABLED = true;

/** Default desk focus when no symbol is selected — never unsuffixed XAUUSD. */
export const TRADING_SYMBOL = WELTRADE_XAUUSD;

export const AUTONOMOUS_QUICK_SYMBOLS = [WELTRADE_XAUUSD] as const;

export const DISABLED_AUTONOMOUS_SYMBOL = "DISABLED_AUTONOMOUS_SYMBOL";

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

export function isAutonomousExecutionSymbol(code: string): boolean {
  return isAllowedTradingSymbol(code);
}

/**
 * Resolve a user/URL symbol for API paths and Terminal state.
 * Gold aliases → ``XAUUSD_i``. Never converts another desk into gold.
 */
export function resolveTradingSymbol(code?: string | null): string {
  const raw = (code || "").trim();
  if (!raw) return TRADING_SYMBOL;

  const inst = raw.match(/^([A-Za-z0-9.]+)[_ ]([iI])$/);
  if (inst) {
    const base = inst[1].toUpperCase().replace(/[^A-Z0-9.]/g, "");
    const broker = `${base}_i`;
    if (isGoldSymbol(base) || isGoldSymbol(broker)) return WELTRADE_XAUUSD;
    return broker;
  }

  const n = normalizeSymbolCode(raw);
  if (DESK_TO_BROKER[n] || isGoldSymbol(raw) || isGoldSymbol(n)) {
    return DESK_TO_BROKER[n] || WELTRADE_XAUUSD;
  }
  if (!MULTI_SYMBOL_ENABLED) {
    return n || raw;
  }
  if (n.endsWith("_I") && n.length > 2) {
    return `${n.slice(0, -2)}_i`;
  }
  return n;
}

/**
 * Map a user search string to an MT5 `q` param.
 * Gold-only: non-gold queries return null → empty result set.
 */
export function goldOnlySearchQuery(q?: string): string | null {
  const raw = (q || "").trim().toUpperCase();
  if (MULTI_SYMBOL_ENABLED) {
    if (!raw) return "";
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
  if (!raw) return WELTRADE_XAUUSD;
  if (
    GOLD_SYMBOL.includes(raw) ||
    raw.includes("XAU") ||
    raw.includes("GOLD") ||
    isGoldSymbol(raw)
  ) {
    return WELTRADE_XAUUSD;
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

/** Operator-facing catalogue label. Wire/API symbol stays XAUUSD_i. */
export function displayTradingSymbol(symbol: string): string {
  const raw = (symbol || "").trim();
  if (!raw) return "—";
  if (isGoldSymbol(raw)) return AUTONOMOUS_BADGE;
  return raw;
}

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
