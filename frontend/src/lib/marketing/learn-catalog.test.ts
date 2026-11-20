import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { LEARN_PAGES, learnPath } from "./learn-catalog.ts";

const root = dirname(fileURLToPath(import.meta.url));
const catalog = readFileSync(join(root, "learn-catalog.ts"), "utf8");
const sitemap = readFileSync(join(root, "../../app/sitemap.ts"), "utf8");
const robots = readFileSync(join(root, "../../app/robots.ts"), "utf8");
const growthPage = readFileSync(
  join(root, "../../app/(app)/admin/growth/page.tsx"),
  "utf8",
);

assert.equal(LEARN_PAGES.length, 7);
const lifecycle = LEARN_PAGES.find((page) => page.slug === "decision-lifecycle");
assert.ok(lifecycle);
assert.match(lifecycle.title, /decision word/i);
assert.match(
  lifecycle.sections.map((section) => section.paragraphs.join(" ")).join(" "),
  /ORDER_SENT/,
);
assert.match(
  lifecycle.sections.map((section) => section.paragraphs.join(" ")).join(" "),
  /NOT_REACHED/,
);
assert.doesNotMatch(
  lifecycle.sections.map((section) => section.paragraphs.join(" ")).join(" "),
  /ORDER_SENT means the broker filled/i,
);
const slugs = new Set(LEARN_PAGES.map((page) => page.slug));
assert.equal(slugs.size, LEARN_PAGES.length);
for (const page of LEARN_PAGES) {
  assert.ok(page.title.length > 8);
  assert.ok(page.faqs.length >= 2);
  assert.equal(learnPath(page.slug), `/learn/${page.slug}`);
}

const banned = [
  /guaranteed profit/i,
  /risk-free/i,
  /win rate/i,
  /\d+(\.\d+)?%/,
  /free trial is available/i,
];
for (const pattern of banned) {
  assert.equal(pattern.test(catalog), false, pattern.source);
}

assert.match(sitemap, /\/learn/);
assert.match(sitemap, /learnPath/);
assert.doesNotMatch(sitemap, /lastModified:/);
assert.match(robots, /\/learn/);
assert.match(growthPage, /Not connected/);
assert.match(growthPage, /Unavailable/);
assert.match(growthPage, /cannot start a check/);
assert.doesNotMatch(growthPage, /Release stop|Run check|setEmergencyStop/);
assert.doesNotMatch(growthPage, /\$[1-9]\d{2,}/);
assert.doesNotMatch(growthPage, /sample metric|demo data/i);

console.log("learn-catalog.test.ts: ok");
