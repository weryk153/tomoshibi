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
test("previewMotion 先 ensureLoaded 再 playOnce，播成功回 'played'", async () => {
  const { renderer, motionCalls, ensureCalls } = makeRenderer();
  const result = await renderer.previewMotion("wave");
  assert.deepEqual(ensureCalls, ["wave"]);
  assert.deepEqual(motionCalls, [["wave", 1]]);
  assert.equal(result, "played");
});

test("previewMotion 在 ensureLoaded 失敗（角色沒有這個 .vrma）時不播放，回 'missing'", async () => {
  const { renderer, motionCalls, ensureCalls } = makeRenderer({ ensureLoaded: async () => false });
  const result = await renderer.previewMotion("no-such-clip");
  assert.deepEqual(ensureCalls, ["no-such-clip"]);
  assert.deepEqual(motionCalls, []);
  assert.equal(result, "missing");
});

// 連點兩個動作：先點的 clip 載入比較慢。沒有世代號的話，它載完後會 playOnce
// 蓋掉後點的那個——使用者看到的是自己最後點的動作沒播、播的是前一個。而且
// 舊呼叫回 false 還會讓元件彈出「這個角色沒有這個動作」的假錯誤。
test("previewMotion：慢的那次被後來的取代時不播放，回 'superseded'", async () => {
  const gates: Record<string, () => void> = {};
  const { renderer, motionCalls } = makeRenderer({
    ensureLoaded: (clip: string) => new Promise<boolean>((resolve) => {
      gates[clip] = (): void => resolve(true);
    }),
  });

  const slow = renderer.previewMotion("slow");   // 先點，載入慢
  const fast = renderer.previewMotion("fast");   // 後點，載入快
  gates.fast();
  assert.equal(await fast, "played");
  gates.slow();                                   // 慢的這時才回來
  assert.equal(await slow, "superseded");

  // 關鍵：慢的那次不能播出去，否則畫面上放的是使用者已經放棄的那個動作。
  assert.deepEqual(motionCalls, [["fast", 1]]);
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

// 空檔時的臉：resetExpression 回到她的心情（resting），不再一律清空。
// currentEmotion 照真實的 ExpressionController 模擬：setEmotion 成功就變那個名字，
// clear() 變 null——setRestingExpression 的「臉被接管了就不要搶回去」靠這個判斷。
function restingRenderer(modelHasIt: boolean) {
  const calls: unknown[][] = [];
  let current: string | null = null;
  const expressions = {
    get currentEmotion(): string | null {
      return current;
    },
    setEmotion: (name: string, intensity: number): boolean => {
      calls.push(["set", name, intensity]);
      if (modelHasIt) current = name;
      return modelHasIt;
    },
    clear: (): void => {
      calls.push(["clear"]);
      current = null;
    },
  } as unknown as ExpressionController;
  const renderer = new VRMRenderer({} as unknown as VRM, {} as unknown as MotionPlayer, expressions);
  return { renderer, calls };
}

test("resting 表情：resetExpression 回到她的心情，強度照給（權重 0.7×強度在 ExpressionController）", () => {
  const { renderer, calls } = restingRenderer(true);
  renderer.setRestingExpression("sad", 0.4);
  renderer.resetExpression();
  assert.deepEqual(calls, [["set", "sad", 0.4]]);
});

test("沒有 resting：resetExpression 清回素顏（跟以前一樣）", () => {
  const { renderer, calls } = restingRenderer(true);
  renderer.setRestingExpression(null, 0);
  renderer.resetExpression();
  assert.deepEqual(calls, [["clear"]]);
});

test("強度 0 等於沒有 resting", () => {
  const { renderer, calls } = restingRenderer(true);
  renderer.setRestingExpression("sad", 0);
  renderer.resetExpression();
  assert.deepEqual(calls, [["clear"]]);
});

test("模型沒有那個表情：退回清空", () => {
  const { renderer, calls } = restingRenderer(false);
  renderer.setRestingExpression("sad", 0.4);
  renderer.resetExpression();
  assert.deepEqual(calls, [["set", "sad", 0.4], ["clear"]]);
});

// fix round 1：avatar.tsx 的 10 秒重算，表情沒換只是強度淡掉時不會再呼叫
// resetExpression()（見 mood.ts 的 shouldApplyResting），新強度要在
// setRestingExpression 自己推進去——但只有目前顯示的臉確實還是 resting 本人才推。
test("強度淡掉、表情沒換：setRestingExpression 自己把新強度推進去，不用呼叫 resetExpression", () => {
  const { renderer, calls } = restingRenderer(true);
  renderer.setRestingExpression("sad", 0.4);
  renderer.resetExpression(); // 先讓畫面真的顯示 sad
  calls.length = 0;
  renderer.setRestingExpression("sad", 0.1); // 同一個表情，強度淡了
  assert.deepEqual(calls, [["set", "sad", 0.1]]);
});

test("臉被試播接管後：淡掉的新強度不會把它搶回來", () => {
  const { renderer, calls } = restingRenderer(true);
  renderer.setRestingExpression("sad", 0.4);
  renderer.resetExpression(); // 畫面顯示 sad
  renderer.previewExpression("joy"); // 使用者在設定頁試播，接管了臉
  calls.length = 0;
  renderer.setRestingExpression("sad", 0.1); // 心情還是 sad，只是強度淡了
  assert.deepEqual(calls, []); // 不是目前顯示的那個，不推
});
