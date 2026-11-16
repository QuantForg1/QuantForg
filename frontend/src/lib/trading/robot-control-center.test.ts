/**
 * Robot Control Center contracts: nav position, backend-confirmed state,
 * account-scoped API, no position closing.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { robotStateLabel, robotStateTone } from "./robot-control.ts";

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
assert.match(page, /never closed by these controls/);
assert.doesNotMatch(page, /close_position|closePosition/);

assert.equal(robotStateLabel("EMERGENCY_STOPPED"), "Emergency stopped");
assert.equal(robotStateTone("PAUSED"), "warning");
assert.equal(robotStateTone("RUNNING"), "success");

console.log("robot-control-center contract ok");
