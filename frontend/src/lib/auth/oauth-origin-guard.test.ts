/**
 * OAuth production origin guards.
 * Run: node --experimental-strip-types src/lib/auth/oauth-origin-guard.test.ts
 */
import assert from "node:assert/strict";
import {
  assertProductionOAuthOrigins,
  authorizeUrlHasLocalhostRedirect,
  isQuantforgProductionHost,
} from "./oauth-origin-guard.ts";

assert.equal(isQuantforgProductionHost("www.quantforg.com"), true);
assert.equal(isQuantforgProductionHost("quantforg.com"), true);
assert.equal(isQuantforgProductionHost("localhost"), false);

assert.equal(
  authorizeUrlHasLocalhostRedirect(
    "https://example.supabase.co/auth/v1/authorize?provider=google&redirect_to=http%3A%2F%2Flocalhost%3A3000%2Fauth%2Fcallback",
  ),
  true,
);
assert.equal(
  authorizeUrlHasLocalhostRedirect(
    "https://example.supabase.co/auth/v1/authorize?provider=google&redirect_to=https%3A%2F%2Fwww.quantforg.com%2Fauth%2Fcallback",
  ),
  false,
);

assert.throws(
  () =>
    assertProductionOAuthOrigins({
      hostname: "www.quantforg.com",
      clientOrigin: "http://localhost:3000",
      authorizeUrl:
        "https://example.supabase.co/auth/v1/authorize?redirect_to=https%3A%2F%2Fwww.quantforg.com%2Fauth%2Fcallback",
    }),
  /localhost/,
);

assert.throws(
  () =>
    assertProductionOAuthOrigins({
      hostname: "www.quantforg.com",
      clientOrigin: "https://www.quantforg.com",
      authorizeUrl:
        "https://example.supabase.co/auth/v1/authorize?redirect_to=http%3A%2F%2Flocalhost%3A3000%2Fauth%2Fcallback",
    }),
  /localhost redirect/,
);

assert.doesNotThrow(() =>
  assertProductionOAuthOrigins({
    hostname: "www.quantforg.com",
    clientOrigin: "https://www.quantforg.com",
    authorizeUrl:
      "https://example.supabase.co/auth/v1/authorize?redirect_to=https%3A%2F%2Fwww.quantforg.com%2Fauth%2Fcallback",
  }),
);

console.log("oauth-origin-guard ok");