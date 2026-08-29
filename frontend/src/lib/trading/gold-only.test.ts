/**
 * Broker-discovered frontend symbol policy.
 * Run: node --experimental-strip-types src/lib/trading/gold-only.test.ts
 */
import assert from "node:assert/strict";
import {
  AUTONOMOUS_BADGE,
  AUTONOMOUS_DISPLAY,
  AUTONOMOUS_QUICK_SYMBOLS,
  AUTONOMOUS_SYMBOL,
  DISABLED_AUTONOMOUS_SYMBOL,
  MULTI_SYMBOL_ENABLED,
  TRADING_SYMBOL,
  WELTRADE_XAUUSD,
  filterTradingSymbolRecords,
  goldOnlySearchQuery,
  isAllowedTradingSymbol,
  isAutonomousExecutionSymbol,
  resolveTradingSymbol,
  displayTradingSymbol,
} from "./gold-only.ts";

assert.equal(MULTI_SYMBOL_ENABLED, true);
assert.equal(AUTONOMOUS_SYMBOL, "XAUUSD_i");
assert.equal(TRADING_SYMBOL, WELTRADE_XAUUSD);
assert.equal(AUTONOMOUS_DISPLAY, "XAUUSD (Gold)");
assert.equal(AUTONOMOUS_BADGE, "XAUUSD · GOLD");
assert.deepEqual([...AUTONOMOUS_QUICK_SYMBOLS], ["XAUUSD_i"]);
assert.equal(DISABLED_AUTONOMOUS_SYMBOL, "DISABLED_AUTONOMOUS_SYMBOL");

assert.equal(isAllowedTradingSymbol("XAUUSD_i"), true);
assert.equal(isAllowedTradingSymbol("XAUUSD"), true);
assert.equal(isAllowedTradingSymbol("EURUSD"), true);
assert.equal(isAutonomousExecutionSymbol("XAUUSD_i"), true);
assert.equal(resolveTradingSymbol("XAUUSD"), "XAUUSD_i");
assert.equal(resolveTradingSymbol("XAUUSD_I"), "XAUUSD_i");
assert.equal(resolveTradingSymbol(""), "XAUUSD_i");
assert.notEqual(resolveTradingSymbol("EURUSD"), "XAUUSD_i");

assert.equal(goldOnlySearchQuery("EURUSD"), "EURUSD");
assert.equal(goldOnlySearchQuery("XAU"), "XAUUSD_i");
assert.equal(goldOnlySearchQuery(""), "");

const filtered = filterTradingSymbolRecords([
  { code: "XAUUSD_i" },
  { code: "EURUSD" },
  { symbol: "GBPUSD" },
  { code: "BTCUSD" },
]);
assert.equal(filtered.length, 4);

assert.equal(displayTradingSymbol("XAUUSD_i"), AUTONOMOUS_BADGE);
assert.equal(displayTradingSymbol("XAUUSD_I"), AUTONOMOUS_BADGE);
assert.equal(displayTradingSymbol("XAUUSD"), AUTONOMOUS_BADGE);

console.log("gold-only.test.ts ok");
