/**
 * XAUUSD-only autonomous frontend policy.
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

assert.equal(MULTI_SYMBOL_ENABLED, false);
assert.equal(AUTONOMOUS_SYMBOL, "XAUUSD_i");
assert.equal(TRADING_SYMBOL, WELTRADE_XAUUSD);
assert.equal(AUTONOMOUS_DISPLAY, "XAUUSD (Gold)");
assert.equal(AUTONOMOUS_BADGE, "XAUUSD · GOLD");
assert.deepEqual([...AUTONOMOUS_QUICK_SYMBOLS], ["XAUUSD_i"]);
assert.equal(DISABLED_AUTONOMOUS_SYMBOL, "DISABLED_AUTONOMOUS_SYMBOL");

assert.equal(isAllowedTradingSymbol("XAUUSD_i"), true);
assert.equal(isAllowedTradingSymbol("XAUUSD"), true);
assert.equal(isAutonomousExecutionSymbol("XAUUSD_i"), true);
assert.equal(resolveTradingSymbol("XAUUSD"), "XAUUSD_i");
assert.equal(resolveTradingSymbol("XAUUSD_I"), "XAUUSD_i");
assert.equal(resolveTradingSymbol(""), "XAUUSD_i");

const rejected = ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "ETHUSD", "NAS100", "US30"];
for (const code of rejected) {
  assert.equal(isAllowedTradingSymbol(code), false, code);
  assert.equal(isAutonomousExecutionSymbol(code), false, code);
  assert.notEqual(resolveTradingSymbol(code), "XAUUSD_i", `must not convert ${code}`);
}

assert.equal(goldOnlySearchQuery("EURUSD"), null);
assert.equal(goldOnlySearchQuery("XAU"), "XAUUSD_i");
assert.equal(goldOnlySearchQuery(""), "XAUUSD_i");

const filtered = filterTradingSymbolRecords([
  { code: "XAUUSD_i" },
  { code: "EURUSD" },
  { symbol: "GBPUSD" },
  { code: "BTCUSD" },
]);
assert.deepEqual(
  filtered.map((r) => String(r.code ?? r.symbol)),
  ["XAUUSD_i"],
);

assert.equal(displayTradingSymbol("XAUUSD_i"), AUTONOMOUS_BADGE);
assert.equal(displayTradingSymbol("XAUUSD_I"), AUTONOMOUS_BADGE);
assert.equal(displayTradingSymbol("XAUUSD"), AUTONOMOUS_BADGE);

console.log("gold-only.test.ts ok");
