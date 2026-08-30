/**
 * Phase 69 — honest signal level presentation + connection presentation.
 */
import assert from "node:assert/strict";
import {
  presentLevel,
  presentPrice,
  resolveConnectionPresentation,
} from "./trader-ux.ts";

assert.equal(presentPrice(null), "Price unavailable");
assert.equal(presentPrice("UNKNOWN"), "Price unavailable");
assert.match(presentPrice(149.25), /^149\.25/);

assert.equal(presentLevel(null, "Entry"), "Entry unavailable");
assert.equal(presentLevel("", "SL"), "SL unavailable");
assert.match(presentLevel(1.085, "TP"), /^1\.085/);

const disconnected = resolveConnectionPresentation({
  ux_state: "NO_BROKER",
  broker: "Disconnected",
});
assert.equal(disconnected.connected, false);
assert.equal(disconnected.label, "BROKER NOT CONNECTED");

const connected = resolveConnectionPresentation({
  ux_state: "CONNECTED",
  broker: "Connected",
  ownership: "owned",
  owned: true,
  account: "12***99",
  server: "Weltrade-Real",
  connection: "Healthy",
});
assert.equal(connected.connected, true);
assert.equal(connected.ownership, "owned");

console.log("phase69-trader-ux-admin: ok");
