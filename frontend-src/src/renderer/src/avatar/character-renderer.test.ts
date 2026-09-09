import assert from "node:assert/strict";
import test from "node:test";
import {
  getActiveRenderer,
  isClipMotion,
  registerRenderer,
  type CharacterRenderer,
} from "./character-renderer.ts";

function fake(): CharacterRenderer {
  return { beginSegment() {}, stop() {}, resetExpression() {} };
}

test("註冊後可取得，註銷後為 null", () => {
  const r = fake();
  const unregister = registerRenderer(r);
  assert.equal(getActiveRenderer(), r);
  unregister();
  assert.equal(getActiveRenderer(), null);
});

test("舊 renderer 晚到的註銷不會清掉新的", () => {
  const a = fake();
  const b = fake();
  const unregisterA = registerRenderer(a);
  registerRenderer(b);
  unregisterA();
  assert.equal(getActiveRenderer(), b);
});

test("isClipMotion 分辨兩種動作格式", () => {
  assert.equal(isClipMotion({ clip: "wave" }), true);
  assert.equal(isClipMotion({ group: "", index: 3 }), false);
});
