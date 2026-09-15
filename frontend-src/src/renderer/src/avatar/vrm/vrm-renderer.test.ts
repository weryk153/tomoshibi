import assert from "node:assert/strict";
import test from "node:test";
import { VRMRenderer } from "./vrm-renderer.ts";
import type { ExpressionController } from "./expression-controller.ts";
import type { MotionPlayer } from "./motion-player.ts";
import type { VRM } from "@pixiv/three-vrm";

// ExpressionController／MotionPlayer 都拿假的——這裡只驗 VRMRenderer 的兩個
// 試播方法有把呼叫轉過去、強度固定 1，不驗真實的表情淡入淡出或動畫播放
// （那是 expression-controller.test.ts／motion-player 自己的責任）。
function makeRenderer(): {
  renderer: VRMRenderer;
  expressionCalls: [string, number][];
  motionCalls: [string, number][];
} {
  const expressionCalls: [string, number][] = [];
  const motionCalls: [string, number][] = [];
  const expressions = {
    setEmotion: (name: string, intensity: number): boolean => {
      expressionCalls.push([name, intensity]);
      return true;
    },
  } as unknown as ExpressionController;
  const motions = {
    playOnce: (clip: string, intensity: number): boolean => {
      motionCalls.push([clip, intensity]);
      return true;
    },
  } as unknown as MotionPlayer;
  const vrm = {} as unknown as VRM;
  const renderer = new VRMRenderer(vrm, motions, expressions);
  return { renderer, expressionCalls, motionCalls };
}

test("previewExpression 轉呼叫 ExpressionController.setEmotion，強度固定 1", () => {
  const { renderer, expressionCalls } = makeRenderer();
  renderer.previewExpression("joy");
  assert.deepEqual(expressionCalls, [["joy", 1]]);
});

test("previewMotion 轉呼叫 MotionPlayer.playOnce，強度固定 1", () => {
  const { renderer, motionCalls } = makeRenderer();
  renderer.previewMotion("wave");
  assert.deepEqual(motionCalls, [["wave", 1]]);
});

test("previewExpression／previewMotion 互不影響對方的呼叫紀錄", () => {
  const { renderer, expressionCalls, motionCalls } = makeRenderer();
  renderer.previewExpression("sad");
  renderer.previewMotion("nod");
  assert.deepEqual(expressionCalls, [["sad", 1]]);
  assert.deepEqual(motionCalls, [["nod", 1]]);
});
