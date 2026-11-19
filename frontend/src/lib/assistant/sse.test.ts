import assert from "node:assert/strict";
import { parseSseFrame, streamBaseCandidates } from "./sse.ts";

assert.deepEqual(parseSseFrame('event: delta\ndata: {"text":"Hi"}'), { event: "delta", data: { text: "Hi" } });
assert.equal(parseSseFrame("event: meta"), null);
assert.equal(parseSseFrame("data: not-json"), null);
assert.equal(parseSseFrame('data: {"a":1}')?.event, "message");

assert.deepEqual(
  streamBaseCandidates("https://api.example.com/api/v1/", "https://www.quantforg.com/qf-api/api/v1"),
  ["https://api.example.com/api/v1", "https://www.quantforg.com/qf-api/api/v1"],
);
assert.deepEqual(streamBaseCandidates("https://a.com/api/v1", "https://a.com/api/v1"), ["https://a.com/api/v1"]);
assert.deepEqual(streamBaseCandidates("/api/v1", "/api/v1"), ["/api/v1"]);

console.log("assistant sse: ok");
