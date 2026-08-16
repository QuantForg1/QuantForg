/**
 * Lightweight Node assert suite for Mission Control health hysteresis.
 * Run: node --experimental-strip-types src/lib/trading/component-health.test.ts
 * (or via npx tsx if available)
 */

import assert from "node:assert/strict";
import {
  mergePlaneOk,
  overlayExecutiveStatus,
  parseTradingComponentsPayload,
  planeConnectionLabel,
  resetTradingComponentsLastGood,
  resolveTradingComponentsView,
} from "./component-health";

resetTradingComponentsLastGood();

const healthyPayload = {
  statuses: { gateway: "HEALTHY", mt5: "CONNECTED", oms: "HEALTHY", ai: "HEALTHY" },
  gateway: { status: "HEALTHY", detail: "ok", evidence: { latency_ms: 120 } },
  mt5: { status: "CONNECTED", detail: "ok", evidence: { connected: true } },
  oms: { status: "HEALTHY", detail: "ok" },
  ai: { status: "HEALTHY", detail: "ok" },
};

const parsed = parseTradingComponentsPayload(healthyPayload, 1_000);
assert.equal(parsed?.gateway.ok, true);
assert.equal(parsed?.mt5.ok, true);
assert.equal(planeConnectionLabel(true), "Connected");
assert.equal(planeConnectionLabel(false), "Disconnected");
assert.equal(planeConnectionLabel(null), "Unknown");

// Hysteresis: timeout keeps last-known-good Connected
const stale = resolveTradingComponentsView({
  isError: true,
  errorKind: "timeout",
  now: 1_000 + 30_000,
});
assert.equal(stale?.gateway.ok, true);
assert.equal(stale?.gateway.stale, true);
assert.equal(planeConnectionLabel(stale!.gateway.ok, stale!.gateway.stale), "Connected (cached)");

// Authoritative healthy beats secondary session-down
assert.equal(mergePlaneOk(true, false), true);
assert.equal(mergePlaneOk(false, true), false);
assert.equal(mergePlaneOk(null, true), true);
assert.equal(mergePlaneOk(null, false), false);
assert.equal(mergePlaneOk(null, null), null);

// Executive overlay: trading-components Connected overrides control-center disconnected
assert.equal(
  overlayExecutiveStatus("disconnected", { ok: true, status: "HEALTHY", detail: "", latencyMs: null, stale: false }),
  "Connected",
);
assert.equal(
  overlayExecutiveStatus("up", { ok: null, status: "UNKNOWN", detail: "", latencyMs: null, stale: false }),
  "Connected",
);
assert.equal(
  overlayExecutiveStatus("disconnected", { ok: null, status: "UNKNOWN", detail: "", latencyMs: null, stale: false }),
  "Disconnected",
);

resetTradingComponentsLastGood();
console.log("component-health.test.ts: ok");
