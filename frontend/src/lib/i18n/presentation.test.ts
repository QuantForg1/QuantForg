import assert from "node:assert/strict";
import {
  formatMoney,
  formatNumber,
  formatZonedDateTime,
  localeSupport,
  paymentMethodSupport,
} from "./presentation.ts";

assert.equal(localeSupport("en-US").supported, true);
assert.equal(localeSupport("fr-FR").supported, false);
assert.equal(localeSupport("fr-FR").reason, "language_not_verified");
assert.equal(formatMoney(49, "USD").includes("USD"), true);
assert.equal(formatMoney(49, "usd"), "Unavailable");
assert.equal(formatMoney(Number.NaN, "USD"), "Unavailable");
assert.equal(formatNumber(1000.5).includes("1"), true);
assert.equal(formatZonedDateTime("not-a-date", "UTC"), "Unavailable");
assert.equal(formatZonedDateTime("2026-11-20T18:00:00Z", "Not/AZone"), "Unavailable");
assert.ok(formatZonedDateTime("2026-11-20T18:00:00Z", "UTC").length > 0);
assert.equal(paymentMethodSupport("crypto"), "verified");
assert.equal(paymentMethodSupport("card"), "unsupported");
console.log("presentation ok");
