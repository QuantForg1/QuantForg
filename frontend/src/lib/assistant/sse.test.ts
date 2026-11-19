import assert from "node:assert/strict";
import { parseSseFrame } from "./sse.ts";

assert.deepEqual(parseSseFrame('event: delta\ndata: {"text":"Hi"}'), { event: "delta", data: { text: "Hi" } });
assert.equal(parseSseFrame("event: meta"), null);
assert.equal(parseSseFrame("data: not-json"), null);
assert.equal(parseSseFrame('data: {"a":1}')?.event, "message");

console.log("assistant sse: ok");
