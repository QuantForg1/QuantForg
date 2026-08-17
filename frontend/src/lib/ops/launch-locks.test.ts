/**
 * Launch-lock helper tests.
 * Run: node --experimental-strip-types src/lib/ops/launch-locks.test.ts
 */
import assert from "node:assert/strict";
import { firstBlockingLock, isExecutionBlockingLock } from "./launch-locks";

assert.equal(isExecutionBlockingLock({ passed: false, blocks_execution: true }), true);
assert.equal(isExecutionBlockingLock({ passed: false, blocks_execution: false }), false);
assert.equal(isExecutionBlockingLock({ passed: true, blocks_execution: true }), false);

const first = firstBlockingLock(
  [
    { key: "broker", passed: false, blocks_execution: false, label: "Broker" },
    { key: "gateway", passed: false, blocks_execution: true, label: "Gateway" },
  ],
);
assert.equal(first?.key, "gateway");

const fromApi = firstBlockingLock(
  [{ key: "gateway", passed: false, blocks_execution: true }],
  { key: "gateway", label: "Gateway", execution_code: "GATEWAY_OFFLINE" },
);
assert.equal(fromApi?.execution_code, "GATEWAY_OFFLINE");

console.log("launch-locks.test.ts: ok");
