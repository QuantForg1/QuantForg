import assert from "node:assert/strict";
import { parseInline, parseMarkdown } from "./markdown.ts";

assert.deepEqual(parseInline("Price **2,650.10** now"), [
  { text: "Price ", bold: false },
  { text: "2,650.10", bold: true },
  { text: " now", bold: false },
]);

const blocks = parseMarkdown(
  "## Trend\nPrice is up.\n\n- Support **2640**\n- Resistance 2660\n1. Wait\n2. Enter\n---\n<script>x</script>",
);
assert.equal(blocks[0].kind, "heading");
assert.equal(blocks[1].kind, "paragraph");
assert.equal(blocks[2].kind, "bullets");
assert.equal(blocks[2].kind === "bullets" && blocks[2].items.length, 2);
assert.equal(blocks[3].kind === "numbered" && blocks[3].items.length, 2);
assert.equal(blocks[4].kind, "rule");
// raw HTML stays plain text (rendered as text, never as HTML)
assert.equal(blocks[5].kind === "paragraph" && blocks[5].inline[0].text, "<script>x</script>");

// nested bullets stay nested under their parent
const nested = parseMarkdown("- Momentum is weak:\n  - M15 RSI **38.5**\n  - H1 RSI 31.4\n- Next point");
assert.equal(nested.length, 1);
assert.equal(nested[0].kind, "bullets");
if (nested[0].kind === "bullets") {
  assert.equal(nested[0].items.length, 2);
  assert.equal(nested[0].items[0].children.length, 2);
  assert.equal(nested[0].items[0].children[0][1].text, "38.5");
}
// "### " headings
const h3 = parseMarkdown("### Key levels");
assert.equal(h3[0].kind === "heading" && h3[0].level, 3);

// links: http(s) only, never javascript:
const link = parseInline("See [Reuters](https://www.reuters.com/x) now");
assert.equal(link[1].href, "https://www.reuters.com/x");
assert.equal(link[1].text, "Reuters");
const bad = parseInline("[x](javascript:alert(1))");
assert.ok(bad.every((p) => !p.href));

console.log("assistant markdown: ok");
