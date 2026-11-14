/**
 * Trader History desk must be reachable at /history (not redirected to /executions).
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../../");
const nextConfig = readFileSync(join(root, "next.config.ts"), "utf8");
const historyPage = readFileSync(
  join(root, "src/app/(app)/history/page.tsx"),
  "utf8",
);
const navConfig = readFileSync(
  join(root, "src/components/layout/nav-config.ts"),
  "utf8",
);

assert.match(historyPage, /title=\"History\"/);
assert.match(navConfig, /href: \"\/history\"/);
assert.match(navConfig, /label: \"History\"/);
assert.equal(
  /source:\s*\"\/history\"[\s\S]*?destination:\s*\"\/executions\"/.test(nextConfig),
  false,
  "/history must not redirect to /executions",
);

console.log("history-route: ok");
