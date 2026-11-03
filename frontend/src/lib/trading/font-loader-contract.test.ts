/**
 * Turbopack production builds fail when the same next/font/google family is
 * loaded twice ("queries have exactly one entry"). Pin a single IBM Plex Sans.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const layout = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "../../app/layout.tsx"),
  "utf8",
);

const plexSansCalls = layout.match(/IBM_Plex_Sans\s*\(/g) ?? [];
assert.equal(
  plexSansCalls.length,
  1,
  "layout.tsx must call IBM_Plex_Sans exactly once for Turbopack-safe builds",
);
assert.match(layout, /IBM_Plex_Mono\s*\(/);
assert.equal(layout.includes("variable: \"--font-display\""), false);

console.log("font-loader-contract: ok");
