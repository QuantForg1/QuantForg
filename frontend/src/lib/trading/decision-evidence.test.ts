import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  decisionTone,
  evidenceText,
  orderExecutionLabel,
} from "./decision-evidence.ts";

assert.equal(evidenceText(null), "Not available");
assert.equal(evidenceText("  "), "Not available");
assert.equal(evidenceText("BUY"), "BUY");
assert.equal(decisionTone("BUY"), "buy");
assert.equal(decisionTone("SELL"), "sell");
assert.equal(decisionTone("WAIT"), "neutral");
assert.equal(orderExecutionLabel({ orderExecuted: false, orderSent: false }), "Not executed");
assert.equal(
  orderExecutionLabel({ orderExecuted: false, orderSent: true }),
  "Order sent — fill not recorded",
);
assert.equal(orderExecutionLabel({ orderExecuted: true }), "Order filled");

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const desk = readFileSync(
  join(root, "components/trading/decision-evidence-desk.tsx"),
  "utf8",
);
const page = readFileSync(join(root, "app/(app)/decision-evidence/page.tsx"), "utf8");
const signals = readFileSync(
  join(root, "components/trading/signals-workspace.tsx"),
  "utf8",
);

assert.match(desk, /grid-cols-1/);
assert.match(desk, /lg:grid-cols-2/);
assert.match(desk, /min-h-\[220px\]/);
assert.match(desk, /Awaiting engine evidence/);
assert.match(desk, /Not available/);
assert.match(desk, /not proof that an order was executed/i);
assert.doesNotMatch(desk, /orderApi|order_send|placeOrder|confidence score/i);
assert.match(page, /signalsAccess/);
assert.match(page, /SignalsLockedView/);
assert.match(signals, /href="\/decision-evidence"/);
assert.doesNotMatch(signals, /Why this signal/);

console.log("decision evidence ui ok");
