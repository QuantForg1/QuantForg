import assert from "node:assert/strict";
import { filterMarketplace, marketplaceEntries } from "./catalog.ts";

const entries = marketplaceEntries({
  items: [
    { key: "gold-trend", name: "Gold trend", category: "trend", description: "Uses supplied bars." },
    { key: "", name: "Dropped" },
    { performance: "verified_live", key: "no-claim", name: "No claim" },
  ],
});
assert.equal(entries.length, 2);
assert.equal(entries[0]?.performance, "unavailable");
assert.equal(entries[1]?.performance, "unavailable");
assert.equal(entries.every((entry) => entry.salesEnabled === false), true);
assert.equal(filterMarketplace(entries, "gold", "").length, 1);
assert.equal(filterMarketplace(entries, "", "missing").length, 0);
console.log("marketplace catalog ok");
