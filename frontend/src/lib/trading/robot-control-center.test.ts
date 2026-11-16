/**
 * Robot Control Center contracts: nav position, backend-confirmed state,
 * account-scoped API, no position closing.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  connectionStateLabel,
  connectionStateTone,
  editableRiskFields,
  robotStateLabel,
  robotStateTone,
  robotStatusTone,
} from "./robot-control.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const nav = readFileSync(join(root, "components/layout/nav-config.ts"), "utf8");
const page = readFileSync(
  join(root, "app/(app)/robot-control-center/page.tsx"),
  "utf8",
);

// Immediately above Risk Center in the primary rail and desk order.
const rcc = nav.indexOf('href: "/robot-control-center"');
const risk = nav.indexOf('href: "/risk-center"');
assert.ok(rcc > 0 && risk > rcc, "Robot Control Center precedes Risk Center");
assert.match(nav, /"\/robot-control-center",\n\s+"\/risk-center",/);

// State shown comes from the backend response, not from the click.
assert.match(page, /robotControlApi\.act/);
assert.match(page, /asRecord\(res\)\.state/);
assert.match(page, /never close open positions/);
assert.doesNotMatch(page, /close_position|closePosition/);

assert.equal(robotStateLabel("EMERGENCY_STOPPED"), "Emergency stopped");
assert.equal(robotStateTone("PAUSED"), "warning");
assert.equal(robotStateTone("RUNNING"), "success");

// Connected is never shown as allowed to trade.
assert.equal(connectionStateTone("TRADING_PERMISSION_DISABLED"), "danger");
assert.match(connectionStateLabel("CONNECTED"), /unknown/);
assert.equal(connectionStateTone("ROBOT_READY"), "success");
assert.match(page, /connectionStateLabel/);

// Customer UI never shows owner-only policy values or labels.
for (const banned of [
  /Owner risk policy/i,
  /OWNER_MIN_REWARD_RISK|OWNER_MAX_SPREAD|OWNER_SESSION_LABEL/,
  /ticket-risk/,
  /after spread/i,
  /Quality ≥/,
  /\$0\.45|≤ \$/,
]) {
  assert.doesNotMatch(page, banned);
}

// "Running" only comes from the backend status code.
assert.equal(robotStateLabel("RUNNING"), "Enabled");
assert.equal(robotStatusTone("ROBOT_RUNNING"), "success");
assert.equal(robotStatusTone("WAITING"), "warning");
assert.equal(robotStatusTone(""), "neutral");
assert.match(connectionStateLabel("UNAVAILABLE"), /unavailable/i);
assert.notEqual(connectionStateTone("UNAVAILABLE"), "success");

// Only backend-configurable risk fields are editable; no ceilings shown.
const fields = editableRiskFields({
  planned_risk_pct: { label: "Risk", help: "h", unit: "percent", configurable: true },
  max_lot: { label: "Lot", help: "h", unit: "lots", configurable: false },
});
assert.deepEqual(
  fields.map((f) => f.key),
  ["planned_risk_pct"],
);
assert.doesNotMatch(page, /bound\.max|\.max\b/);

console.log("robot-control-center contract ok");
