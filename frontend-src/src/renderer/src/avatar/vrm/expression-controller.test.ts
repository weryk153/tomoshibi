import assert from "node:assert/strict";
import test from "node:test";
import { ExpressionController, type ExpressionSink } from "./expression-controller.ts";

function sink(names: string[]) {
  const values: Record<string, number> = {};
  const s: ExpressionSink & { values: Record<string, number> } = {
    values,
    has: (n) => names.includes(n),
    setValue: (n, w) => { values[n] = w; },
  };
  return s;
}

const close = (a: number, b: number) => Math.abs(a - b) < 1e-6;

test("情緒 0.2 秒淡入", () => {
  const s = sink(["happy", "aa"]);
  const c = new ExpressionController(s, 0.2);
  assert.equal(c.setEmotion("happy"), true);
  c.update(0.1);
  assert.ok(close(s.values.happy, 0.5));
  c.update(0.1);
  assert.ok(close(s.values.happy, 1));
  c.update(1);
  assert.ok(close(s.values.happy, 1));
});

test("換情緒：舊的淡出、新的淡入同時進行", () => {
  const s = sink(["happy", "sad", "aa"]);
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy");
  c.update(0.2);
  c.setEmotion("sad");
  c.update(0.1);
  assert.ok(close(s.values.happy, 0.5));
  assert.ok(close(s.values.sad, 0.5));
  c.update(0.1);
  assert.ok(close(s.values.happy, 0));
  assert.ok(close(s.values.sad, 1));
});

test("clear 把所有情緒淡到 0", () => {
  const s = sink(["happy", "aa"]);
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy");
  c.update(0.2);
  c.clear();
  c.update(0.2);
  assert.ok(close(s.values.happy, 0));
});

test("未知名字：回 false、不改變現狀、只警告一次", () => {
  const s = sink(["happy", "aa"]);
  const c = new ExpressionController(s, 0.2);
  const warns: string[] = [];
  const orig = console.warn;
  console.warn = (...a: unknown[]) => { warns.push(String(a[0])); };
  try {
    c.setEmotion("happy");
    c.update(0.2);
    assert.equal(c.setEmotion("nope"), false);
    assert.equal(c.setEmotion("nope"), false);
    c.update(0.1);
    assert.ok(close(s.values.happy, 1));
    assert.equal(warns.length, 1);
  } finally {
    console.warn = orig;
  }
});

test("嘴型每幀直接寫 aa", () => {
  const s = sink(["aa"]);
  const c = new ExpressionController(s, 0.2);
  c.setMouth(0.7);
  c.update(0.016);
  assert.ok(close(s.values.aa, 0.7));
});
