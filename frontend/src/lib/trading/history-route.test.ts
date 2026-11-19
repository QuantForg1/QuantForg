/**
 * The trader History desk is retired. /history opens Book, never Executions.
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

assert.match(historyPage, /redirect\("\/book"\)/);
assert.equal(navConfig.includes('href: "/history"'), false);
assert.equal(navConfig.includes('label: "History"'), false);
const historyRedirect = nextConfig.match(
  /\{\s*source:\s*"\/history",\s*destination:\s*"([^"]+)"/,
);
assert.equal(historyRedirect?.[1], "/book");

console.log("history-route: ok");
