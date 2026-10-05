import assert from "node:assert/strict";
import test from "node:test";
import { hasLive2DExpression } from "./use-live2d-expression.ts";

// fix round 1：live2d-renderer.ts 的 resetExpression 要先知道模型有沒有這個表情，
// 才能在沒有時退回清空（跟 VRM 的 setEmotion 回 false 是同一個道理）。
function fakeAdapter(names: string[]) {
  return {
    getExpressionCount: () => names.length,
    getExpressionName: (index: number) => names[index] ?? "",
  };
}

test("hasLive2DExpression：字串名字有在表情清單裡就是有", () => {
  const adapter = fakeAdapter(["happy", "sad"]);
  assert.equal(hasLive2DExpression("sad", adapter), true);
  assert.equal(hasLive2DExpression("angry", adapter), false);
});

test("hasLive2DExpression：索引在範圍內、名字不是空字串才算有", () => {
  const adapter = fakeAdapter(["happy", "sad"]);
  assert.equal(hasLive2DExpression(0, adapter), true);
  assert.equal(hasLive2DExpression(1, adapter), true);
  assert.equal(hasLive2DExpression(2, adapter), false);
  assert.equal(hasLive2DExpression(-1, adapter), false);
});

test("hasLive2DExpression：沒有 adapter 或拋例外都當作沒有，不往外丟", () => {
  assert.equal(hasLive2DExpression("sad", null), false);
  const throwing = {
    getExpressionCount: () => { throw new Error("boom"); },
  };
  assert.equal(hasLive2DExpression("sad", throwing), false);
});
