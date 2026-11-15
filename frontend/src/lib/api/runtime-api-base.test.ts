import assert from "node:assert/strict";

/**
 * Mirrors getRuntimeApiBaseUrl Production host selection without importing
 * Next env (keeps the Node unit runner free of NEXT_PUBLIC_ requirements).
 */
function runtimeApiBaseForHost(
  hostname: string,
  origin: string,
  configured: string,
): string {
  const host = hostname.toLowerCase();
  if (host === "www.quantforg.com" || host === "quantforg.com") {
    return `${origin.replace(/\/$/, "")}/qf-api/api/v1`;
  }
  return configured;
}

assert.equal(
  runtimeApiBaseForHost(
    "www.quantforg.com",
    "https://www.quantforg.com",
    "https://quantforg-production.up.railway.app/api/v1",
  ),
  "https://www.quantforg.com/qf-api/api/v1",
);
assert.equal(
  runtimeApiBaseForHost(
    "localhost",
    "http://localhost:3000",
    "https://quantforg-production.up.railway.app/api/v1",
  ),
  "https://quantforg-production.up.railway.app/api/v1",
);

console.log("runtime-api-base ok");
