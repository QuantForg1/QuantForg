import assert from "node:assert/strict";
import { BRAND_ACCENT, BRAND_ASSETS, BRAND_CHARCOAL, BRAND_NAME } from "./assets.ts";

assert.equal(BRAND_NAME, "QuantForg");
assert.equal(BRAND_ACCENT, "#00D4E0");
assert.equal(BRAND_CHARCOAL, "#111827");
assert.equal(BRAND_ASSETS.mark, "/brand/quantforg-mark-256.png");
assert.equal(BRAND_ASSETS.ogImage, "/og-image.png");
for (const key of Object.keys(BRAND_ASSETS) as (keyof typeof BRAND_ASSETS)[]) {
  assert.ok(BRAND_ASSETS[key].startsWith("/"), `${key} must be a root-relative path`);
}
console.log("assets.test.ts: ok");
