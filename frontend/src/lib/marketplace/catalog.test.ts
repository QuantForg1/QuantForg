import assert from "node:assert/strict";
import {
  filterMarketplace,
  findMarketplaceEntry,
  marketplaceEntries,
  PERFORMANCE_LANES,
} from "./catalog.ts";

const entries = marketplaceEntries({
  items: [
    {
      key: "gold-trend",
      name: "Gold trend",
      category: "trend",
      description: "Uses supplied bars.",
      version: "2026.11",
      instrument: "XAUUSD",
    },
    { key: "", name: "Dropped" },
    { performance: { live: 12 }, key: "no-claim", name: "No claim", category: "momentum" },
  ],
});

assert.equal(entries.length, 2);
assert.equal(entries[0]?.performance.live, "unavailable");
assert.equal(entries[1]?.performance.backtest, "unavailable");
assert.equal(entries[0]?.combinedPerformance, null);
assert.equal(entries[0]?.version, "2026.11");
assert.equal(entries[1]?.version, null);
assert.equal(entries.every((entry) => entry.salesEnabled === false), true);
assert.equal(entries.every((entry) => entry.copyTradingEnabled === false), true);
assert.equal(PERFORMANCE_LANES.length, 5);
assert.equal(filterMarketplace(entries, "gold", "").length, 1);
assert.equal(filterMarketplace(entries, "xau", "").length, 1);
assert.equal(filterMarketplace(entries, "", "missing").length, 0);
assert.equal(findMarketplaceEntry(entries, "no-claim")?.name, "No claim");
assert.equal(findMarketplaceEntry(entries, "missing"), null);
console.log("marketplace catalog ok");
