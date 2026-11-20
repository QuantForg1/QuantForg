import assert from "node:assert/strict";
import { figureLabel, statusLabel } from "./performance-label.ts";

assert.equal(figureLabel(undefined), "Unavailable");
assert.equal(figureLabel({ value: null, status: "pending_synchronization" }), "pending synchronization");
assert.equal(figureLabel({ value: "", status: "unavailable" }), "unavailable");
assert.equal(figureLabel({ value: "0", status: "verified" }), "0");
assert.equal(figureLabel({ value: "12.50", status: "verified" }), "12.50");
assert.equal(statusLabel(undefined), "unavailable");
console.log("trust figure labels ok");
