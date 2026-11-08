/**
 * Production builds must self-host IBM Plex via next/font/local (CSP + Vercel
 * reliability). next/font/google fetch failures break Vercel deploys.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const layoutPath = join(here, "../../app/layout.tsx");
const layout = readFileSync(layoutPath, "utf8");

assert.match(layout, /from\s+["']next\/font\/local["']/);
assert.doesNotMatch(layout, /from\s+["']next\/font\/google["']/);
assert.match(layout, /localFont\s*\(/);
assert.match(layout, /IBMPlexSans-Regular\.woff2/);
assert.match(layout, /IBMPlexMono-Regular\.woff2/);
assert.match(layout, /variable:\s*["']--font-sans["']/);
assert.match(layout, /variable:\s*["']--font-mono["']/);
console.log("font-loader-contract: ok");
