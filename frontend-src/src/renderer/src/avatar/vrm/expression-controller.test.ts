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
  // 上限是 EMOTION_MAX 0.7，不是 1——推到 1 會讓 overrideMouth/overrideBlink 的
  // 倍率歸零，笑著講話就不動嘴也不眨眼。
  c.update(0.1);
  assert.ok(close(s.values.happy, 0.7));
  c.update(1);
  assert.ok(close(s.values.happy, 0.7));
});

test("換情緒：舊的淡出、新的淡入同時進行", () => {
  const s = sink(["happy", "sad", "aa"]);
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy");
  c.update(0.2);
  c.setEmotion("sad");
  c.update(0.1);
  assert.ok(close(s.values.happy, 0.2));
  assert.ok(close(s.values.sad, 0.5));
  c.update(0.1);
  assert.ok(close(s.values.happy, 0));
  assert.ok(close(s.values.sad, 0.7));
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
    assert.ok(close(s.values.happy, 0.7));
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

test("情緒宣告 overrideMouth: blend 時，嘴型要先除掉倍率補回來", () => {
  const s = sink(["happy", "aa"]);
  s.overrideMouth = (n) => (n === "happy" ? "blend" : "none");
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy");
  c.setMouth(0.3);
  c.update(1); // happy 直接到 0.7

  // three-vrm 待會會乘上 (1 - 0.7) = 0.3，所以這裡要先寫 0.3 / 0.3 = 1，
  // 相乘後才會回到使用者聽到的那個 0.3。沒有這個補償的話最後只剩 0.09。
  assert.ok(close(s.values.aa, 1));
  assert.ok(close(c.blinkMultiplier(), 1)); // 沒宣告 overrideBlink 就不該被壓
});

test("overrideBlink: blend 的倍率要露出來給 renderer 補", () => {
  const s = sink(["happy", "aa"]);
  s.overrideBlink = (n) => (n === "happy" ? "blend" : "none");
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy");
  c.update(1);
  assert.ok(close(c.blinkMultiplier(), 0.3));
  assert.ok(close(ExpressionController.compensate(0.2, 0.3), 0.2 / 0.3));
});

test("倍率太小就不硬補，免得除出來爆成抖動", () => {
  assert.equal(ExpressionController.compensate(0.5, 0), 0.5);
  assert.equal(ExpressionController.compensate(0.5, 0.01), 0.5);
  // 補償後不會超過 1
  assert.equal(ExpressionController.compensate(0.9, 0.3), 1);
});

test("沒實作 override 查詢的 sink 照舊運作（倍率恆為 1）", () => {
  const s = sink(["happy", "aa"]);
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy");
  c.setMouth(0.4);
  c.update(1);
  assert.ok(close(s.values.aa, 0.4));
  assert.ok(close(c.blinkMultiplier(), 1));
});

test("強度讓同一個表情有層次：0.3 的笑不等於滿的笑", () => {
  const s = sink(["happy", "aa"]);
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy", 0.3);
  c.update(1);
  // 0.7（EMOTION_MAX）× 0.3
  assert.ok(close(s.values.happy, 0.21));
});

test("沒給強度就是最滿（維持舊行為）", () => {
  const s = sink(["happy", "aa"]);
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy");
  c.update(1);
  assert.ok(close(s.values.happy, 0.7));
});

test("強度超出 0..1 要夾住", () => {
  const s = sink(["happy", "aa"]);
  const c = new ExpressionController(s, 0.2);
  c.setEmotion("happy", 5);
  c.update(1);
  assert.ok(close(s.values.happy, 0.7));
  c.setEmotion("happy", -1);
  c.update(1);
  assert.ok(close(s.values.happy, 0));
});
