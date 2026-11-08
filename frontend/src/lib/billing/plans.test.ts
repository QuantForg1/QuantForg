import assert from "node:assert/strict";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatUsd,
  getPlan,
  PAYMENT_METHOD_LABEL,
  TRIAL_DAYS,
} from "./plans.ts";

assert.equal(BILLING_PLANS.length, 3);
assert.equal(BILLING_PLANS[0]?.id, "starter");
assert.equal(BILLING_PLANS[0]?.monthlyPriceUsd, 49);
assert.equal(BILLING_PLANS[1]?.monthlyPriceUsd, 99);
assert.equal(BILLING_PLANS[2]?.monthlyPriceUsd, 199);
assert.equal(BILLING_PLANS[2]?.licenseTier, "enterprise");
assert.equal(ANNUAL_BILLING_SUPPORTED, false);
assert.equal(BILLING_PROVIDER.configured, true);
assert.equal(BILLING_PROVIDER.paymentMethodLabel, "Crypto Payment");
assert.equal(PAYMENT_METHOD_LABEL, "Crypto Payment");
assert.equal(BILLING_PROVIDER.recurringSupported, false);
assert.equal(TRIAL_DAYS, 7);
assert.equal(getPlan("professional")?.name, "Professional");
assert.equal(formatUsd(49), "$49");
assert.ok(!JSON.stringify(BILLING_PROVIDER).includes("NOWPayments"));
console.log("plans.test.ts: ok");
