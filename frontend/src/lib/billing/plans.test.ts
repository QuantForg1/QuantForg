import assert from "node:assert/strict";
import {
  ANNUAL_BILLING_SUPPORTED,
  BILLING_PLANS,
  BILLING_PROVIDER,
  formatUsd,
  getPlan,
  PAYMENT_METHOD_LABEL,
  FREE_TRIAL_AVAILABLE,
  PLAN_COMPARISON_ROWS,
  UNPAID_ACCESS,
} from "./plans.ts";

assert.equal(BILLING_PLANS.length, 3);
assert.equal(BILLING_PLANS[0]?.id, "starter");
assert.equal(BILLING_PLANS[0]?.monthlyPriceUsd, 199);
assert.equal(BILLING_PLANS[1]?.monthlyPriceUsd, 399);
assert.equal(BILLING_PLANS[2]?.monthlyPriceUsd, 799);
assert.equal(BILLING_PLANS[2]?.licenseTier, "enterprise");
assert.equal(ANNUAL_BILLING_SUPPORTED, false);
assert.equal(BILLING_PROVIDER.configured, true);
assert.equal(BILLING_PROVIDER.paymentMethodLabel, "Crypto Payment");
assert.equal(PAYMENT_METHOD_LABEL, "Crypto Payment");
assert.equal(BILLING_PROVIDER.recurringSupported, false);
assert.equal(FREE_TRIAL_AVAILABLE, false);
assert.ok(UNPAID_ACCESS.some((r) => r.feature === "Start the robot" && !r.allowed));
assert.ok(UNPAID_ACCESS.some((r) => r.feature === "Connect your MT5 broker" && r.allowed));
assert.ok(PLAN_COMPARISON_ROWS.every((r) => !("trial" in r)));
assert.equal(getPlan("professional")?.name, "Professional");
assert.equal(formatUsd(199), "$199");
assert.ok(!JSON.stringify(BILLING_PROVIDER).includes("NOWPayments"));
console.log("plans.test.ts: ok");
