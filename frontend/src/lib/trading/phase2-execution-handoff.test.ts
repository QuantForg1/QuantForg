/**
 * Phase 2 execution handoff contracts — signal→Terminal, no comment-tag BE/trail.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { OWNER_MIN_REWARD_RISK } from "../execution/ticket-risk.ts";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const ticket = readFileSync(
  join(root, "components/execution/order-ticket.tsx"),
  "utf8",
);
const detail = readFileSync(
  join(root, "components/trading/intelligence-detail.tsx"),
  "utf8",
);
const shell = readFileSync(join(root, "components/terminal/shell.tsx"), "utf8");
const riskCenter = readFileSync(
  join(root, "app/(app)/risk-center/page.tsx"),
  "utf8",
);

assert.equal(OWNER_MIN_REWARD_RISK, 0.2);
assert.doesNotMatch(ticket, /trail:/);
assert.doesNotMatch(ticket, /be:1/);
assert.doesNotMatch(ticket, /Break even tag/);
assert.match(ticket, /Position Management Engine/);
assert.match(ticket, /prefill/);
assert.match(detail, /Open in Terminal/);
assert.match(shell, /ticketPrefill/);
assert.match(shell, /searchParams\.get\("sl"\)/);
assert.match(riskCenter, /ordersMaySubmit=\{ordersMaySubmit\}/);
assert.doesNotMatch(riskCenter, /ordersMaySubmit=\{undefined\}/);

console.log("phase2-execution-handoff: ok");
