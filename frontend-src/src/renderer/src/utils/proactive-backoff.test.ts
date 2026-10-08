import assert from "node:assert/strict";
import test from "node:test";
import { MAX_UNANSWERED, nextProactiveDelay } from "./proactive-backoff.ts";

test("沒人回就把間隔加倍：1 倍、2 倍、4 倍", () => {
  assert.equal(nextProactiveDelay(60, 0), 60);
  assert.equal(nextProactiveDelay(60, 1), 120);
  assert.equal(nextProactiveDelay(60, 2), 240);
});

test("連續 3 次沒人回就不再開口，等對方說話", () => {
  assert.equal(MAX_UNANSWERED, 3);
  assert.equal(nextProactiveDelay(60, 3), null);
  assert.equal(nextProactiveDelay(60, 7), null);
});

test("設定的秒數低於 30 一樣以 30 秒起算", () => {
  assert.equal(nextProactiveDelay(5, 0), 30);
  assert.equal(nextProactiveDelay(Number.NaN, 1), 60);
});
