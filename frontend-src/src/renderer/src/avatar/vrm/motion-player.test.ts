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
    (player as unknown as { actions: Map<string, { parts: Map<string, THREE.AnimationAction> }> }).actions
      .get(name)!
      .parts.get("core")!;
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

// 每幀 idle 的權重最多只能變這麼多：再大就是一眨眼換姿勢（看起來像彈回去）。
const MAX_STEP = 0.1;

function steps(player: MotionPlayer, idle: () => number, frames: number): number {
  let biggest = 0;
  let last = idle();
  for (let i = 0; i < frames; i++) {
    player.update(1 / 60);
    biggest = Math.max(biggest, Math.abs(idle() - last));
    last = idle();
  }
  return biggest;
}

test("同一個動作連著兩句：還在做的時候再叫一次，不會先掉回 idle 再重來", () => {
  const { player, action, run } = withClips(["idle", 4], ["wave", 2]);
  player.playIdle();
  player.playOnce("wave", 1);
  run(0.8);
  player.playOnce("wave", 1);
  const biggest = steps(player, () => action("idle").getEffectiveWeight(), 30);
  assert.ok(biggest < MAX_STEP, `idle weight jumped ${biggest} in one frame`);
});

test("同一個動作在淡回 idle 時又被叫：平順地再做一次", () => {
  const { player, action, run } = withClips(["idle", 4], ["wave", 2]);
  player.playIdle();
  player.playOnce("wave", 1);
  run(1.6); // 正在淡回
  player.playOnce("wave", 1);
  const biggest = steps(player, () => action("idle").getEffectiveWeight(), 60);
  assert.ok(biggest < MAX_STEP, `idle weight jumped ${biggest} in one frame`);
  assert.ok(action("idle").getEffectiveWeight() < 0.2, "the wave plays again");
});

test("一連串動作（同的、不同的、強弱不一）過程中，姿勢都不會一幀跳開", () => {
  const { player, action } = withClips(["idle", 4], ["wave", 1.5], ["nod", 1.2]);
  player.playIdle();
  const idle = () => action("idle").getEffectiveWeight();
  let biggest = 0;
  for (const [name, intensity, frames] of [
    ["wave", 1, 20], ["wave", 0.6, 50], ["nod", 1, 10], ["nod", 1, 70], ["wave", 0.3, 120],
  ] as [string, number, number][]) {
    player.playOnce(name, intensity);
    biggest = Math.max(biggest, steps(player, idle, frames));
  }
  assert.ok(biggest < MAX_STEP, `idle weight jumped ${biggest} in one frame`);
});

// 有 humanoid 的 VRM：clip 依骨頭拆成軀幹、手臂、頭三份。
function withBody(...clips: [string, number][]) {
  const scene = new THREE.Object3D();
  const bones = ["hips", "spine", "leftUpperArm", "rightUpperArm", "neck", "head"];
  for (const bone of bones) {
    const node = new THREE.Object3D();
    node.name = `N_${bone}`;
    scene.add(node);
  }
  const vrm = {
    scene,
    humanoid: {
      humanBones: Object.fromEntries(bones.map((bone) => [bone, {}])),
      getNormalizedBoneNode: (bone: string) => scene.getObjectByName(`N_${bone}`),
    },
  } as unknown as VRM;
  const player = new MotionPlayer(vrm, "https://example.test/motions");
  const register = (player as unknown as { register(name: string, clip: THREE.AnimationClip): void })
    .register.bind(player);
  for (const [name, seconds] of clips) {
    register(
      name,
      new THREE.AnimationClip(
        name,
        seconds,
        bones.map((bone) => new THREE.QuaternionKeyframeTrack(`N_${bone}.quaternion`, [0, seconds], [0, 0, 0, 1, 0, 0, 0, 1])),
      ),
    );
  }
  const part = (name: string, which: string) =>
    (player as unknown as { actions: Map<string, { parts: Map<string, THREE.AnimationAction> }> }).actions
      .get(name)!
      .parts.get(which)!;
  const run = (seconds: number) => {
    for (let t = 0; t < seconds - 1e-9; t += 1 / 60) player.update(1 / 60);
  };
  return { player, part, run };
}

test("像真人：軀幹先動、手臂跟上、頭最後；回 idle 時軀幹先回、頭最後回", () => {
  const { player, part, run } = withBody(["idle", 6], ["angry", 4]);
  player.playIdle();
  player.playOnce("angry", 1);
  run(0.3);
  const enter = ["core", "arms", "head"].map((p) => part("angry", p).getEffectiveWeight());
  assert.ok(enter[0] > enter[1] && enter[1] > enter[2], `entering ${enter}`);
  run(3.0); // 結束前 0.7 秒左右，正在回
  const back = ["core", "arms", "head"].map((p) => part("angry", p).getEffectiveWeight());
  assert.ok(back[0] < back[1] && back[1] < back[2], `returning ${back}`);
  run(1.0);
  for (const p of ["core", "arms", "head"]) {
    assert.equal(part("angry", p).getEffectiveWeight(), 0);
    assert.equal(part("idle", p).getEffectiveWeight(), 1);
  }
});

test("像真人：進出是先慢後快再慢，不是等速", () => {
  const { player, part } = withBody(["idle", 6], ["angry", 4]);
  player.playIdle();
  player.playOnce("angry", 1);
  const weights: number[] = [];
  for (let i = 0; i < 40; i++) {
    player.update(1 / 60);
    weights.push(part("angry", "core").getEffectiveWeight());
  }
  const steps = weights.slice(1).map((w, i) => w - weights[i]);
  const early = steps[2], middle = steps[17];
  assert.ok(middle > early * 2, `early step ${early}, middle step ${middle}`);
});
