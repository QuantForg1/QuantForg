import assert from "node:assert/strict";
import { isSubscriptionRequiredError, signalsAccess } from "./feature-access.ts";

assert.equal(signalsAccess({ loading: true, error: false, robotAccess: {} }), "checking");
assert.equal(signalsAccess({ loading: false, error: true, robotAccess: {} }), "unknown");
assert.equal(signalsAccess({ loading: false, error: false, robotAccess: {} }), "locked");
assert.equal(
  signalsAccess({ loading: false, error: false, robotAccess: { allowed: false } }),
  "locked",
);
assert.equal(
  signalsAccess({ loading: false, error: false, robotAccess: { allowed: "true" } }),
  "locked",
);
assert.equal(
  signalsAccess({ loading: false, error: false, robotAccess: { allowed: true } }),
  "open",
);

assert.equal(isSubscriptionRequiredError({ status: 402 }), true);
assert.equal(
  isSubscriptionRequiredError({ status: 400, details: { detail: { code: "subscription_required" } } }),
  true,
);
assert.equal(isSubscriptionRequiredError({ status: 500 }), false);
assert.equal(isSubscriptionRequiredError(null), false);

console.log("feature-access: ok");
