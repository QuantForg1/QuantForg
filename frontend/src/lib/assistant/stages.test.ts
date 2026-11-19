import assert from "node:assert/strict";
import { revealRate, revealStep, revealTo, settleStages, upsertStage } from "./stages.ts";

let l = upsertStage([], { key: "price", label: "Reading", status: "active" });
l = upsertStage(l, { key: "price", label: "Reading", detail: "3,675", status: "done" });
l = upsertStage(l, { key: "write", label: "Thinking", status: "active" });
assert.equal(l.length, 2);
assert.equal(l[0].detail, "3,675");
assert.deepEqual(settleStages(l).map((s) => s.status), ["done", "done"]);

assert.equal(revealStep(0), 0);
assert.equal(revealStep(1), 1);
assert.equal(revealStep(10), 2);
assert.equal(revealStep(2400), 100); // catches up when far behind

// steady pace: ~1,000 chars take several seconds, never instant
let shown = 0;
let t = 0;
const text = "word ".repeat(200); // 1,000 chars
let budget = 0;
while (shown < text.length) {
  const dt = 1 / 60;
  t += dt;
  budget += revealRate(text.length - shown) * dt;
  if (budget < 1) continue;
  const next = revealTo(text, shown, budget);
  budget = Math.max(0, budget - (next - shown));
  shown = next;
}
assert.ok(t > 5 && t < 12, `took ${t}s`);
// words appear whole
assert.equal(revealTo("hello world", 0, 2), 0); // wait until "hello" fits
assert.equal(revealTo("hello world", 0, 5), 5);
assert.equal(revealTo("hello world", 0, 11), 11);
assert.equal(revealTo("x".repeat(40), 0, 3), 3); // very long token never stalls

console.log("assistant stages: ok");
