import assert from "node:assert/strict";
import {
  BRAND_ACCENT,
  BRAND_ASSETS,
  BRAND_CHARCOAL,
  BRAND_NAME,
  BRAND_NAVY,
  BRAND_TAGLINE,
  BRAND_TEAL,
} from "./assets.ts";

assert.equal(BRAND_NAME, "QuantForg");
assert.equal(BRAND_TAGLINE, "Institutional AI Trading Platform");
assert.equal(BRAND_ACCENT, "#00D4E0");
assert.equal(BRAND_TEAL, "#00CAC0");
assert.equal(BRAND_NAVY, "#061B35");
assert.equal(BRAND_CHARCOAL, BRAND_NAVY);
assert.equal(BRAND_ASSETS.mark, "/brand/quantforg-mark-256.png");
assert.equal(BRAND_ASSETS.ogImage, "/og-image.png");
assert.equal(BRAND_ASSETS.faviconSvg, "/favicon.svg");
assert.equal(BRAND_ASSETS.mountain, "/brand/mountain-backdrop.jpg");
for (const key of Object.keys(BRAND_ASSETS) as (keyof typeof BRAND_ASSETS)[]) {
  assert.ok(BRAND_ASSETS[key].startsWith("/"), `${key} must be a root-relative path`);
}
console.log("brand assets ok");
