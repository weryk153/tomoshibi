import assert from "node:assert/strict";
import test from "node:test";
import {
  effectiveMood,
  getCharacterMood,
  MOOD_FLOOR,
  moodToKeyword,
  onCharacterMoodChange,
  parseCharacterMood,
  restingExpression,
  restingFor,
  setCharacterMood,
  type CharacterMood,
} from "./mood.ts";

const SAD: CharacterMood = { mood: "sad", intensity: 0.8, updatedAt: 1000, halfLife: 300 };
const close = (a: number, b: number) => Math.abs(a - b) < 1e-9;
const VRM_MAP = { neutral: "neutral", joy: "happy", sadness: "sad", relaxed: "relaxed" };
const FRIEREN_MAP = { sadness: 0, joy: 9, neutral: 12 };

test("parseCharacterMood：後端的欄位名換成前端的", () => {
  assert.deepEqual(
    parseCharacterMood({ type: "character-mood", mood: "sad", intensity: 0.8, updated_at: 1000, half_life: 300 }),
    SAD,
  );
});

test("parseCharacterMood：缺欄位、半衰期不是正數、數字是字串都不收", () => {
  assert.equal(parseCharacterMood({ mood: "sad", intensity: 0.8, updated_at: 1000 }), null);
  assert.equal(parseCharacterMood({ mood: "sad", intensity: 0.8, updated_at: 1000, half_life: 0 }), null);
  assert.equal(parseCharacterMood({ mood: "sad", intensity: "0.8", updated_at: 1000, half_life: 300 }), null);
  assert.equal(parseCharacterMood(null), null);
});

test("parseCharacterMood：強度超出 0..1 夾回來", () => {
  assert.equal(parseCharacterMood({ mood: "sad", intensity: 3, updated_at: 1, half_life: 300 })?.intensity, 1);
});

test("effectiveMood：每過一個半衰期減半", () => {
  for (const [elapsed, expected] of [[0, 0.8], [300, 0.4], [600, 0.2]] as const) {
    const now = effectiveMood(SAD, 1000 + elapsed);
    assert.equal(now.mood, "sad");
    assert.ok(close(now.intensity, expected), `${elapsed}s → ${now.intensity}`);
  }
});

test("effectiveMood：跌破門檻就是 neutral（跟引擎一樣 0.15）", () => {
  assert.equal(MOOD_FLOOR, 0.15);
  assert.deepEqual(effectiveMood(SAD, 1900), { mood: "neutral", intensity: 0 });
});

test("effectiveMood：時間在未來不會變強（另一台機器的時鐘）", () => {
  assert.deepEqual(effectiveMood(SAD, 500), { mood: "sad", intensity: 0.8 });
});

test("effectiveMood：沒有心情、neutral 都是 neutral", () => {
  assert.deepEqual(effectiveMood(null, 1000), { mood: "neutral", intensity: 0 });
  assert.deepEqual(effectiveMood({ ...SAD, mood: "neutral" }, 1000), { mood: "neutral", intensity: 0 });
});

test("moodToKeyword：引擎的八個詞對到 Tomoshibi 的關鍵字", () => {
  assert.deepEqual(
    ["neutral", "happy", "sad", "angry", "surprised", "embarrassed", "calm", "worried"].map(moodToKeyword),
    [null, "joy", "sadness", "anger", "surprise", "embarrassed", "relaxed", "sadness"],
  );
  assert.equal(moodToKeyword("excited"), null);
});

test("restingExpression：照模型的 emotionMap 找表情", () => {
  assert.equal(restingExpression("sad", VRM_MAP), "sad");
  assert.equal(restingExpression("calm", VRM_MAP), "relaxed");
});

test("restingExpression：害羞沒有就退回開心，平靜沒有就退回 neutral", () => {
  assert.equal(restingExpression("embarrassed", VRM_MAP), "happy");
  assert.equal(restingExpression("embarrassed", { ...VRM_MAP, embarrassed: "blush" }), "blush");
  assert.equal(restingExpression("calm", FRIEREN_MAP), 12);
});

test("restingExpression：Live2D 的 0 號是真的表情，不是沒有", () => {
  assert.equal(restingExpression("sad", FRIEREN_MAP), 0);
});

test("restingExpression：退回也找不到、neutral、沒有表就是無", () => {
  assert.equal(restingExpression("angry", FRIEREN_MAP), null);
  assert.equal(restingExpression("neutral", VRM_MAP), null);
  assert.equal(restingExpression("sad", undefined), null);
});

test("restingFor：淡掉的強度跟著表情走；跌破門檻就沒有表情", () => {
  const half = restingFor(SAD, VRM_MAP, 1300);
  assert.equal(half.expression, "sad");
  assert.ok(close(half.intensity, 0.4));
  assert.deepEqual(restingFor(SAD, VRM_MAP, 1900), { expression: null, intensity: 0 });
  assert.deepEqual(restingFor({ ...SAD, mood: "angry" }, FRIEREN_MAP, 1000), { expression: null, intensity: 0 });
});

test("心情倉庫：存、取、通知、取消通知", () => {
  let told = 0;
  const stop = onCharacterMoodChange(() => { told += 1; });
  setCharacterMood(SAD);
  assert.deepEqual(getCharacterMood(), SAD);
  stop();
  setCharacterMood(null);
  assert.equal(getCharacterMood(), null);
  assert.equal(told, 1);
});
