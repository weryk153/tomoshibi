import assert from "node:assert/strict";
import test from "node:test";
import {
  getActiveRenderer,
  isClipMotion,
  onRendererRegistered,
  registerRenderer,
  type CharacterRenderer,
} from "./character-renderer.ts";

function fake(): CharacterRenderer {
  return {
    beginSegment() {}, stop() {}, resetExpression() {}, setRestingExpression() {},
  };
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

// fix round 1：avatar.tsx 進 IDLE 時 renderer 可能還沒註冊好（VRM lazy import），
// 要能在 renderer 一到就補套一次，不用乾等 10 秒的 tick。
test("onRendererRegistered：註冊時收到通知，取消訂閱後不再收到", () => {
  let told = 0;
  const stop = onRendererRegistered(() => { told += 1; });
  const unregister = registerRenderer(fake());
  assert.equal(told, 1);
  stop();
  registerRenderer(fake());
  assert.equal(told, 1);
  unregister();
});

test("onRendererRegistered：不會在註銷時收到通知", () => {
  let told = 0;
  const unregister = registerRenderer(fake());
  const stop = onRendererRegistered(() => { told += 1; });
  unregister();
  assert.equal(told, 0);
  stop();
});

test("isClipMotion 分辨兩種動作格式", () => {
  assert.equal(isClipMotion({ clip: "wave" }), true);
  assert.equal(isClipMotion({ group: "", index: 3 }), false);
});
