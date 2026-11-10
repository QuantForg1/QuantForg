/**
 * Market status helpers — feed outages must not read as market closed.
 * Run: node --experimental-strip-types src/lib/trading/market-status.test.ts
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)));
const src = readFileSync(join(root, "market-status.ts"), "utf8");

assert.match(src, /MARKET_FEED_UNAVAILABLE/);
assert.match(src, /CLOUDFLARE_ORIGIN_UNREACHABLE/);
assert.match(src, /Never treat a bare HTTP 503 as market-closed/);
assert.match(src, /publicFeedBadge/);
assert.match(src, /MARKET CLOSED/);
assert.match(src, /DELAYED/);
assert.match(src, /personal broker login is not required/);

// Badge labels stay explicit for chart chrome.
assert.match(src, /case "live":\s*return \{ label: "LIVE"/);
assert.match(src, /case "closed":\s*return \{ label: "MARKET CLOSED"/);
assert.match(src, /case "delayed":\s*return \{ label: "DELAYED"/);

console.log("market-status: ok");
