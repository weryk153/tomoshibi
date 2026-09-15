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
