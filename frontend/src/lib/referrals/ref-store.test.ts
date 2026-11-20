import assert from "node:assert/strict";

const mem = new Map<string, string>();
(globalThis as unknown as { window: unknown }).window = {
  localStorage: {
    getItem: (k: string) => mem.get(k) ?? null,
    setItem: (k: string, v: string) => void mem.set(k, v),
    removeItem: (k: string) => void mem.delete(k),
  },
};

const { normalizeRefCode, rememberRefCode, pendingRefCode, clearRefCode } = await import("./ref-store.ts");

assert.equal(normalizeRefCode(" ab12cd34 "), "AB12CD34");
assert.equal(normalizeRefCode("bad code!"), null);
assert.equal(normalizeRefCode(""), null);

const t0 = 1_000_000;
assert.equal(rememberRefCode("first1", t0), "FIRST1");
assert.equal(rememberRefCode("second2", t0 + 1000), "FIRST1", "first link wins");
assert.equal(pendingRefCode(t0 + 1000), "FIRST1");
assert.equal(pendingRefCode(t0 + 31 * 24 * 3600 * 1000), null, "expires after 30 days");
clearRefCode();
assert.equal(pendingRefCode(t0), null);
console.log("ref-store: ok");
