import assert from "node:assert/strict";
import test from "node:test";
import { VRMRenderer } from "./vrm-renderer.ts";
import type { ExpressionController } from "./expression-controller.ts";
import type { MotionPlayer } from "./motion-player.ts";
import type { VRM } from "@pixiv/three-vrm";

// ExpressionController／MotionPlayer 都拿假的——這裡只驗 VRMRenderer 的方法有
// 把呼叫轉過去、強度固定 1，不驗真實的表情淡入淡出或動畫播放
// （那是 expression-controller.test.ts／motion-player 自己的責任）。
function makeRenderer(overrides: {
  ensureLoaded?: (clip: string) => Promise<boolean>;
  playOnce?: (clip: string, intensity: number) => boolean;
} = {}): {
  renderer: VRMRenderer;
  expressionCalls: [string, number][];
  motionCalls: [string, number][];
  ensureCalls: string[];
} {
  const expressionCalls: [string, number][] = [];
  const motionCalls: [string, number][] = [];
  const ensureCalls: string[] = [];
  const expressions = {
    setEmotion: (name: string, intensity: number): boolean => {
      expressionCalls.push([name, intensity]);
      return true;
    },
  } as unknown as ExpressionController;
  const motions = {
    ensureLoaded: async (clip: string): Promise<boolean> => {
      ensureCalls.push(clip);
      return overrides.ensureLoaded ? overrides.ensureLoaded(clip) : true;
    },
    playOnce: (clip: string, intensity: number): boolean => {
      motionCalls.push([clip, intensity]);
      return overrides.playOnce ? overrides.playOnce(clip, intensity) : true;
    },
  } as unknown as MotionPlayer;
  const vrm = {} as unknown as VRM;
  const renderer = new VRMRenderer(vrm, motions, expressions);
  return {
    renderer, expressionCalls, motionCalls, ensureCalls,
  };
}

test("previewExpression 轉呼叫 ExpressionController.setEmotion，強度固定 1", () => {
  const { renderer, expressionCalls } = makeRenderer();
  renderer.previewExpression("joy");
  assert.deepEqual(expressionCalls, [["joy", 1]]);
});

// review a0c0ce7 fix 2（important）：VRMAvatar 只預先載入 motionMap 裡目前有的
// clip；試播一個剛存檔、還沒被預先載入的 clip 之前，previewMotion 必須先
// ensureLoaded 現拉一次，不能悄悄什麼都不做。
test("previewMotion 先 ensureLoaded 再 playOnce，回傳 playOnce 的結果", async () => {
  const { renderer, motionCalls, ensureCalls } = makeRenderer();
  const result = await renderer.previewMotion("wave");
  assert.deepEqual(ensureCalls, ["wave"]);
  assert.deepEqual(motionCalls, [["wave", 1]]);
  assert.equal(result, true);
});

test("previewMotion 在 ensureLoaded 失敗（角色沒有這個 .vrma）時不播放，回傳 false", async () => {
  const { renderer, motionCalls, ensureCalls } = makeRenderer({ ensureLoaded: async () => false });
  const result = await renderer.previewMotion("no-such-clip");
  assert.deepEqual(ensureCalls, ["no-such-clip"]);
  assert.deepEqual(motionCalls, []);
  assert.equal(result, false);
});

test("previewExpression／previewMotion 互不影響對方的呼叫紀錄", async () => {
  const { renderer, expressionCalls, motionCalls } = makeRenderer();
  renderer.previewExpression("sad");
  await renderer.previewMotion("nod");
  assert.deepEqual(expressionCalls, [["sad", 1]]);
  assert.deepEqual(motionCalls, [["nod", 1]]);
});

// review a0c0ce7 fix 2(d)：存檔後對每個新指到的 clip 背景預先載入，讓 LLM 接下來
//能立刻觸發、不用等使用者先按一次試播。轉呼叫 MotionPlayer.ensureLoaded，不播放
// （跟 previewMotion 不同，這裡不該讓角色憑空動一下）。
test("ensureMotionLoaded 轉呼叫 MotionPlayer.ensureLoaded，不觸發 playOnce", async () => {
  const { renderer, motionCalls, ensureCalls } = makeRenderer();
  const result = await renderer.ensureMotionLoaded("greet");
  assert.deepEqual(ensureCalls, ["greet"]);
  assert.deepEqual(motionCalls, []);
  assert.equal(result, true);
});
