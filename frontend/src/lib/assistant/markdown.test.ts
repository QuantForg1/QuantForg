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

console.log("assistant markdown: ok");
