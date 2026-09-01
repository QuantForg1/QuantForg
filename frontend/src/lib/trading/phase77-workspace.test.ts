/**
 * Phase 77 — dashboard/session isolation, broker rail, signals terminal.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  TRADER_DESK_ORDER,
  visiblePrimaryRail,
} from "../../components/layout/nav-config.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const dash = readFileSync(join(root, "app/(app)/dashboard/page.tsx"), "utf8");
const signals = readFileSync(
  join(root, "components/trading/signals-workspace.tsx"),
  "utf8",
);
const signalCard = readFileSync(
  join(root, "components/trading/signal-card.tsx"),
  "utf8",
);
const broker = readFileSync(
  join(root, "components/broker/broker-config-workspace.tsx"),
  "utf8",
);
const detail = readFileSync(
  join(root, "components/trading/intelligence-detail.tsx"),
  "utf8",
);

assert.equal(dash.includes("Unable to load your trading session."), false);
assert.match(dash, /Trading session temporarily unavailable/);
assert.match(dash, /Research and signals remain independent/);
assert.match(dash, /QuantForg workspace/);

assert.match(signals, /GLOBAL MARKET SIGNALS/);
assert.match(signals, /SignalCard/);
assert.match(signalCard, /Stop loss/);
assert.match(signalCard, /Take profit/);
assert.match(signalCard, /signalExecutionStatusLabel/);
assert.match(signalCard, /signalMt5Ticket/);
assert.equal(signals.includes("Why this signal"), false);
assert.match(signals, /Research does not require a personal MT5 session/);

assert.match(broker, /Connect MT5/);
assert.match(broker, /Live trading/);
assert.match(broker, /Password is never displayed/);
assert.equal(broker.includes("password="), false);
assert.equal(/\bhunter2\b/.test(broker), false);

assert.equal(detail.includes("Why this signal"), false);
assert.match(detail, /signalHumanExplanation/);

const rail = visiblePrimaryRail(true);
assert.ok(rail.some((item) => item.href === "/broker"));
assert.ok(rail.every((item) => item.href !== "/admin"));
assert.equal(
  rail.find((item) => item.href === "/broker")?.section,
  "Trading",
);
assert.equal(
  rail.find((item) => item.href === "/dashboard")?.section,
  "Workspace",
);
assert.ok(TRADER_DESK_ORDER.includes("/broker"));

console.log("phase77-workspace: ok");
