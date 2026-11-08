import assert from "node:assert/strict";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatUsd,
  getPlan,
} from "./plans.ts";

assert.equal(BILLING_PLANS.length, 3);
assert.equal(BILLING_PLANS[0]?.id, "starter");
assert.equal(BILLING_PLANS[0]?.monthlyPriceUsd, 49);
assert.equal(BILLING_PLANS[1]?.monthlyPriceUsd, 99);
assert.equal(BILLING_PLANS[2]?.monthlyPriceUsd, 199);
assert.equal(BILLING_PLANS[2]?.licenseTier, "enterprise");
assert.equal(ANNUAL_BILLING_SUPPORTED, false);
assert.equal(BILLING_PROVIDER.configured, false);
assert.equal(getPlan("professional")?.name, "Professional");
assert.equal(formatUsd(49), "$49");
console.log("plans.test.ts: ok");
