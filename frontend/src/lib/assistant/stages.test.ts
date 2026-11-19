import assert from "node:assert/strict";
import { revealStep, settleStages, upsertStage } from "./stages.ts";

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

console.log("assistant stages: ok");
