import assert from "node:assert/strict";
import { friendlyLoadMessage } from "./friendly-error.ts";

assert.equal(friendlyLoadMessage("Strategy Lab could not be loaded."), "Reconnecting to Strategy Lab…");
assert.equal(friendlyLoadMessage("The news and economic-calendar feeds could not be loaded."), "Reconnecting to news and economic-calendar feeds…");
assert.equal(friendlyLoadMessage("Unable to load this resource."), "Reconnecting…");
assert.equal(friendlyLoadMessage("Signals access was removed."), "Signals access was removed.");
console.log("friendly-error: ok");
