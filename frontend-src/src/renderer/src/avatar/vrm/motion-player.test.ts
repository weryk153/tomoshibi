import assert from "node:assert/strict";
import test from "node:test";
import * as THREE from "three";
import { MotionPlayer } from "./motion-player.ts";
import type { VRM } from "@pixiv/three-vrm";

// 真的建構 MotionPlayer（不是假物件）：這裡要測的是 ensureLoaded 自己的
// dedup／不快取失敗邏輯，那段程式碼就活在這個類別本身，沒有介面可以繞過去。
// AnimationMixer 只需要一個 Object3D 當 root，不需要 DOM／WebGL，node 底下
// 可以直接建構（跟 vrm-renderer.test.ts 的「假 MotionPlayer」不同，那邊測的是
// VRMRenderer 有沒有轉呼叫，這裡測的是 MotionPlayer 自己）。
function makePlayer(): MotionPlayer {
  const vrm = { scene: new THREE.Object3D() } as unknown as VRM;
  return new MotionPlayer(vrm, "https://example.test/motions");
}

// load() 打真的 GLTFLoader／網路，這裡用一個假的同名方法蓋掉實例上的
// this.load，讓 ensureLoaded 的呼叫轉給它，不用真的拉檔案。
function stubLoad(
  player: MotionPlayer,
  impl: (name: string, url: string) => Promise<boolean>,
): { calls: string[] } {
  const calls: string[] = [];
  (player as unknown as { load: typeof impl }).load = (name, url) => {
    calls.push(name);
    return impl(name, url);
  };
  return { calls };
}

test("ensureLoaded：兩個同時發生的呼叫只觸發一次 load（dedupe in-flight）", async () => {
  const player = makePlayer();
  let resolveLoad: (v: boolean) => void = () => {};
  const { calls } = stubLoad(player, () => new Promise((resolve) => { resolveLoad = resolve; }));

  const p1 = player.ensureLoaded("wave");
  const p2 = player.ensureLoaded("wave");
  resolveLoad(true);
  const [r1, r2] = await Promise.all([p1, p2]);

  assert.equal(calls.length, 1);
  assert.deepEqual(calls, ["wave"]);
  assert.equal(r1, true);
  assert.equal(r2, true);
});

test("ensureLoaded：不同 clip 的並發呼叫各自觸發自己的 load，不會互相 dedupe", async () => {
  const player = makePlayer();
  const { calls } = stubLoad(player, async () => true);

  await Promise.all([player.ensureLoaded("wave"), player.ensureLoaded("nod")]);

  assert.deepEqual([...calls].sort(), ["nod", "wave"]);
});

test("ensureLoaded：不快取失敗——settle 後從 pending map 移除，下一次呼叫會重新 load", async () => {
  const player = makePlayer();
  let attempt = 0;
  const { calls } = stubLoad(player, async () => {
    attempt += 1;
    return attempt > 1; // 第一次失敗，第二次成功
  });

  const first = await player.ensureLoaded("wave");
  const second = await player.ensureLoaded("wave");

  assert.equal(first, false);
  assert.equal(second, true);
  assert.equal(calls.length, 2);
});

// 換角色時 vrm-avatar.tsx 的 cleanup 會呼叫 dispose()。GLTFLoader.loadAsync 不收
// AbortSignal，所以飛在路上的請求一定會回來——沒有 disposed 旗標的話，它會在
// 已經 stopAllAction 的 mixer 上 clipAction() 重建 action 並塞回 actions，讓
// hasClip() 對一個死掉的 mixer 回 true。
test("dispose：飛行中的 load 回來時不再回填 actions", async () => {
  const player = makePlayer();
  let resolveLoad: (v: unknown) => void = () => {};
  // 蓋掉真的 GLTFLoader：回一個「有動畫」的 gltf，讓 load() 走到 disposed 檢查
  // 那一行。若旗標沒擋住，下一行 createVRMAnimationClip 會拿假 VRM 去用。
  (player as unknown as { loader: { loadAsync: () => Promise<unknown> } }).loader = {
    loadAsync: () => new Promise((resolve) => { resolveLoad = resolve; }),
  };

  const pending = player.ensureLoaded("wave");
  player.dispose();
  resolveLoad({ userData: { vrmAnimations: [{}] } });

  assert.equal(await pending, false);
  assert.equal(player.hasClip("wave"), false);
});

test("dispose 之後 ensureLoaded 直接回 false，不再起新的請求", async () => {
  const player = makePlayer();
  const { calls } = stubLoad(player, async () => true);

  player.dispose();
  const result = await player.ensureLoaded("wave");

  assert.equal(result, false);
  assert.deepEqual(calls, []);
});

// ---------------------------------------------------------------- 回到 idle

// 用真的 AnimationMixer 跑手做的 clip：要看的是每幀的權重，不需要真的 .vrma。
function clip(name: string, seconds: number): THREE.AnimationClip {
  return new THREE.AnimationClip(name, seconds, [
    new THREE.NumberKeyframeTrack(".position[x]", [0, seconds], [0, 1]),
  ]);
}

function withClips(...clips: [string, number][]) {
  const player = makePlayer();
  const register = (player as unknown as { register(name: string, clip: THREE.AnimationClip): void })
    .register.bind(player);
  for (const [name, seconds] of clips) register(name, clip(name, seconds));
  const action = (name: string) =>
    (player as unknown as { actions: Map<string, THREE.AnimationAction> }).actions.get(name)!;
  const run = (seconds: number) => {
    for (let t = 0; t < seconds - 1e-9; t += 1 / 60) player.update(1 / 60);
  };
  return { player, action, run };
}

test("idle 與動作的權重加起來一直是 1：強度 0.5 不會混進 T-pose", () => {
  const { player, action, run } = withClips(["idle", 4], ["wave", 2]);
  player.playIdle();
  run(0.5);
  player.playOnce("wave", 0.5);
  for (let i = 0; i < 150; i++) {
    run(1 / 60);
    const sum = action("idle").getEffectiveWeight() + action("wave").getEffectiveWeight();
    assert.ok(Math.abs(sum - 1) < 1e-6, `sum ${sum} at frame ${i}`);
  }
});

test("動作快結束時就開始淡回 idle，播完時已經回到 idle", () => {
  const { player, action, run } = withClips(["idle", 4], ["wave", 2]);
  player.playIdle();
  player.playOnce("wave", 1);
  run(1.6); // 結束前 0.4 秒
  const leaving = action("wave").getEffectiveWeight();
  assert.ok(leaving < 0.9 && leaving > 0, `wave weight ${leaving}`);
  run(0.5);
  assert.equal(action("wave").getEffectiveWeight(), 0);
  assert.equal(action("idle").getEffectiveWeight(), 1);
});

test("回 idle 是慢慢淡回去，不是一兩幀就彈回去", () => {
  const { player, action, run } = withClips(["idle", 4], ["wave", 3]);
  player.playIdle();
  player.playOnce("wave", 1);
  const weights: number[] = [];
  for (let i = 0; i < 200; i++) {
    run(1 / 60);
    weights.push(action("wave").getEffectiveWeight());
  }
  const falling = weights.filter((w, i) => i > 60 && w > 0.02 && w < 0.98).length;
  assert.ok(falling >= 30, `only ${falling} frames between full and gone`); // ≥ 0.5 秒
});

test("idle 不會因為動作而從頭重來", () => {
  const { player, action, run } = withClips(["idle", 4], ["wave", 1]);
  player.playIdle();
  run(1.0);
  player.playOnce("wave", 1);
  run(1.5);
  assert.ok(action("idle").time > 2.0, `idle time ${action("idle").time}`);
});

test("回覆講完（stop）不會打斷還在做的動作", () => {
  const { player, action, run } = withClips(["idle", 4], ["wave", 2]);
  player.playIdle();
  player.playOnce("wave", 1);
  run(0.5);
  player.stop();
  run(0.3);
  assert.ok(action("wave").getEffectiveWeight() > 0.9);
});

test("動作中換下一個動作：舊的淡出、新的淡入，總和仍是 1", () => {
  const { player, action, run } = withClips(["idle", 4], ["wave", 3], ["nod", 3]);
  player.playIdle();
  player.playOnce("wave", 1);
  run(0.5);
  player.playOnce("nod", 0.8);
  run(0.1);
  const w = action("wave").getEffectiveWeight();
  const n = action("nod").getEffectiveWeight();
  assert.ok(w > 0 && w < 1 && n > 0 && n < 0.8, `wave ${w} nod ${n}`);
  assert.ok(Math.abs(w + n + action("idle").getEffectiveWeight() - 1) < 1e-6);
  run(1.0);
  assert.equal(action("wave").getEffectiveWeight(), 0);
  assert.ok(Math.abs(action("nod").getEffectiveWeight() - 0.8) < 1e-6);
});
