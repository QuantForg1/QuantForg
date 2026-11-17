import assert from "node:assert/strict";

import { isBrokerSessionUnknown } from "./session-status.ts";

const base = {
  hasData: false,
  isLoading: false,
  isError: false,
  changingAccount: false,
};

// Loading or failed with no data: unknown, never "disconnected".
assert.equal(isBrokerSessionUnknown({ ...base, isLoading: true }), true);
assert.equal(isBrokerSessionUnknown({ ...base, isError: true }), true);
// Stale data during a failed refetch keeps the last known state.
assert.equal(
  isBrokerSessionUnknown({ ...base, hasData: true, isError: true }),
  false,
);
// Explicit "Change account" always shows the form.
assert.equal(
  isBrokerSessionUnknown({ ...base, isError: true, changingAccount: true }),
  false,
);
// Settled with data: the backend decides.
assert.equal(isBrokerSessionUnknown({ ...base, hasData: true }), false);

console.log("broker session-status tests passed");
