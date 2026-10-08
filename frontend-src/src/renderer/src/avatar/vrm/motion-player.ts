// frontend-src/src/renderer/src/avatar/vrm/motion-player.ts
// .vrma 動畫：idle 迴圈 + LLM 觸發的 one-shot。
//
// idle 一直在播、從不重來；動作疊在上面，每幀的權重由這裡算（不用 three.js
// 的 fadeIn/fadeOut）。idle 的權重永遠是 1 減掉動作的，所以強度 0.5 的揮手是
// 「一半揮手、一半 idle」，不會混進 T-pose；回覆講完也不打斷還在做的動作。
//
// 像真人：每個 clip 依身體拆成軀幹、手臂、頭頸三份，各自一個 action。進出都用
// 先慢、中快、後慢的曲線（ENTER／RETURN 秒），軀幹先動、手臂晚一點、頭最後
// （DELAY）；結束前就開始淡回，播完時剛好回到 idle。TK256 這類動作是「擺一個
// 情緒姿勢並維持」，頭尾離 idle 都有 15–35 度，等速、全身同時的內插看起來像機器。
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { VRM } from "@pixiv/three-vrm";
import {
  VRMAnimationLoaderPlugin,
  createVRMAnimationClip,
  type VRMAnimation,
} from "@pixiv/three-vrm-animation";

export const IDLE_CLIP = "idle";
type Part = "core" | "arms" | "head";
const PARTS: Part[] = ["core", "arms", "head"];
// 進入動作、回到 idle 各花多久（短的 clip 按比例縮短）。
const ENTER = 0.6;
const RETURN = 1.2;
// 各部位比軀幹晚多久開始（3 秒以上的 clip；短的按比例縮短）。
const DELAY: Record<Part, number> = { core: 0, arms: 0.12, head: 0.25 };
const ARM_BONES = ["Shoulder", "UpperArm", "LowerArm", "Hand", "Thumb", "Index", "Middle", "Ring", "Little"];
const HEAD_BONES = ["neck", "head", "leftEye", "rightEye", "jaw"];

function boneOf(name: string): Part {
  if (HEAD_BONES.includes(name)) return "head";
  if (/^(left|right)/.test(name) && ARM_BONES.some((part) => name.includes(part))) return "arms";
  return "core";
}

// 先慢、中快、後慢。
function ease(x: number): number {
  const t = Math.max(0, Math.min(1, x));
  return t * t * (3 - 2 * t);
}

// 一個 clip 的一份（本尊或複本）：同一個 clip 的各部位一起播、時間一致。
type Instance = { name: string; parts: Map<Part, THREE.AnimationAction>; duration: number };
// peak 是要的強度，level 是這一幀的強度（往 peak 慢慢靠，強度改了也不會跳）。
type Gesture = { instance: Instance; peak: number; level: number; weights: Map<Part, number> };
// 被下一個動作換掉的：跟新動作的淡入互補著淡出，加起來不超過 1。
type Leaving = {
  instance: Instance;
  from: Map<Part, number>;
  weights: Map<Part, number>;
  elapsed: number;
  timing: Timing;
};
type Timing = { enter: number; ret: number; delays: Map<Part, number>; last: number };

function timingOf(instance: Instance): Timing {
  const duration = instance.duration;
  const scale = Math.min(1, duration / 3);
  const delays = new Map<Part, number>();
  const several = instance.parts.size > 1;
  for (const part of instance.parts.keys()) delays.set(part, several ? DELAY[part] * scale : 0);
  return {
    enter: Math.min(ENTER, duration * 0.25),
    ret: Math.min(RETURN, duration * 0.35),
    delays,
    last: Math.max(0, ...delays.values()),
  };
}

export class MotionPlayer {
  private mixer: THREE.AnimationMixer;
  private actions = new Map<string, Instance>();
  private gesture: Gesture | null = null;
  private leaving: Leaving[] = [];
  // 同一個動作還在淡出時又要做一次，就用它的複本淡入：同一個 action 不能
  // 同時淡出又從頭開始（reset 會讓它一幀之內跳回第一格、權重歸零）。
  private copies = new Map<string, Instance[]>();
  private loader = new GLTFLoader();
  private readonly vrm: VRM;
  // review a0c0ce7 fix 2：VRMAvatar 只在角色載入時預先讀 motionMap 裡當下有的
  // clip（見 vrm-avatar.tsx）。存檔後新增的關鍵字，或還沒被試播過的 clip，都要
  // 能用這個 base URL 現拉，不用整個角色重新載入。
  private readonly motionsBaseUrl: string;
  // re-review of cfa0138 殘留 2：試播鍵可能在同一個 clip 上被連點，或存檔後
  // ensureMotionLoaded 對同一批 clip 觸發、使用者又立刻按了試播——這些都是對
  // 「同一個 clip」的並發 ensureLoaded。沒有這個 map 的話每次呼叫都各自起一個
  // GLTFLoader 請求，同一個檔案被拉好幾份。key 是 clip 名稱，value 是那次
  // load() 呼叫本身的 promise；settle（無論成功失敗）就從這裡刪掉，所以「失敗」
  // 不會被快取住——下一次呼叫會重新嘗試，跟 hasClip 為 true 時的「成功有快取」
  // 是不同語意（成功的快取活在 this.actions，不在這個 map）。
  private pendingLoads = new Map<string, Promise<boolean>>();
  // dispose() 之後就不准再碰 mixer／actions。ensureLoaded 起的那次網路請求沒有
  // abort 的辦法（GLTFLoader.loadAsync 不收 signal），所以換角色時飛在路上的
  // load() 一定會回來——沒有這個旗標的話它會在已經 stopAllAction 的 mixer 上
  // clipAction() 重建 action 並塞回 this.actions，讓 hasClip() 對一個死掉的
  // mixer 回 true，整個舊 player 也被請求吊著無法回收。
  private disposed = false;

  // 明確欄位指派而不是 constructor parameter property：vrm-renderer.ts 對這個檔案
  // 是值匯入（IDLE_CLIP），node --test 載入 vrm-renderer.test.ts 時會連帶解析整份
  // 這個檔案，parameter property 語法會讓 node --experimental-strip-types 直接
  // SyntaxError（見 frontend-node-test-constraints）。行為不變。
  constructor(vrm: VRM, motionsBaseUrl: string) {
    this.vrm = vrm;
    this.motionsBaseUrl = motionsBaseUrl;
    this.mixer = new THREE.AnimationMixer(vrm.scene);
    this.loader.register((parser) => new VRMAnimationLoaderPlugin(parser));
  }

  async load(name: string, url: string): Promise<boolean> {
    try {
      const gltf = await this.loader.loadAsync(url);
      const anims = (gltf.userData as { vrmAnimations?: VRMAnimation[] }).vrmAnimations ?? [];
      if (!anims.length) {
        console.warn(`[VRM] ${url} has no VRM animation`);
        return false;
      }
      // await 之後才檢查：請求飛行期間可能已經換角色並 dispose 過了。
      if (this.disposed) return false;
      this.register(name, createVRMAnimationClip(anims[0], this.vrm));
      return true;
    } catch (e) {
      console.warn(`[VRM] failed to load motion ${name}:`, e);
      return false;
    }
  }

  private register(name: string, clip: THREE.AnimationClip): void {
    this.actions.set(name, this.instanceOf(name, clip));
  }

  /** 這個 clip 拆成各部位的 action（沒有 humanoid 的話整份算軀幹）。 */
  private instanceOf(name: string, clip: THREE.AnimationClip): Instance {
    const partOfNode = new Map<string, Part>();
    const humanoid = (this.vrm as Partial<VRM>).humanoid;
    if (humanoid) {
      for (const bone of Object.keys(humanoid.humanBones ?? {})) {
        const node = humanoid.getNormalizedBoneNode(bone as never);
        if (node?.name) partOfNode.set(node.name, boneOf(bone));
      }
    }
    const tracks = new Map<Part, THREE.KeyframeTrack[]>();
    for (const track of clip.tracks) {
      const node = THREE.PropertyBinding.parseTrackName(track.name).nodeName;
      // 視線、表情的 track 跟著頭；認不出的跟著軀幹。
      const part = partOfNode.get(node) ?? (/lookat|expression/i.test(node) ? "head" : "core");
      tracks.set(part, [...(tracks.get(part) ?? []), track]);
    }
    const parts = new Map<Part, THREE.AnimationAction>();
    for (const part of PARTS) {
      const own = tracks.get(part);
      if (!own) continue;
      const action = this.mixer.clipAction(new THREE.AnimationClip(`${name}:${part}`, clip.duration, own));
      if (name === IDLE_CLIP) {
        action.setLoop(THREE.LoopRepeat, Number.POSITIVE_INFINITY);
      } else {
        action.setLoop(THREE.LoopOnce, 1);
        action.clampWhenFinished = true;
      }
      parts.set(part, action);
    }
    return { name, parts, duration: clip.duration };
  }

  hasClip(name: string): boolean {
    return this.actions.has(name);
  }

  /**
   * 確保某個 clip 已經載入，已經有就直接回 true 不重拉。給試播（可能點到一個
   * 剛存檔、角色載入當下還不知道要拉的 clip）與存檔後的背景預先載入用。
   *
   * 對同一個 name 的並發呼叫會共用同一次 load()（見 pendingLoads 欄位的說明），
   * 不會各自起一份請求；那次請求 settle 後就從 pendingLoads 移除，所以失敗
   * 不會被快取，下一次呼叫會重新嘗試。
   */
  async ensureLoaded(name: string): Promise<boolean> {
    if (this.disposed) return false;
    if (this.hasClip(name)) return true;
    const pending = this.pendingLoads.get(name);
    if (pending) return pending;
    const promise = this.load(name, `${this.motionsBaseUrl}/${name}.vrma`);
    this.pendingLoads.set(name, promise);
    promise.finally(() => this.pendingLoads.delete(name));
    return promise;
  }

  /** 讓 idle 開始播（已經在播就不動，不會從頭來）。 */
  playIdle(): void {
    const idle = this.actions.get(IDLE_CLIP);
    if (!idle) return;
    for (const [part, action] of idle.parts) {
      if (action.isRunning()) continue;
      action.setEffectiveWeight(Math.max(0, 1 - this.otherWeight(part)));
      action.play();
    }
  }

  /**
   * `intensity` 是「這個動作做多大」，0..1，預設 1：權重不滿時 idle 從底下補
   * 上，所以 0.4 的揮手就是小幅度的揮手，而不是另外準備一個小幅度的片段。
   */
  playOnce(name: string, intensity = 1): boolean {
    const base = this.actions.get(name);
    if (!base) {
      console.warn(`[VRM] motion clip "${name}" not loaded; staying idle`);
      return false;
    }
    // 太小的話動作幾乎看不見，卻仍然佔著「正在播動作」的狀態擋住 idle，
    // 看起來就只是僵住。低於這個值直接當作沒有這個動作。
    if (intensity < 0.05) return false;
    const peak = Math.max(0, Math.min(1, intensity));
    const previous = this.gesture;
    if (previous && previous.instance.name === name && !this.returning(previous)) {
      // 還在做同一個動作：接著做，只換強度（慢慢換）。
      previous.peak = peak;
      return true;
    }
    const next = this.freeInstance(name, base);
    const timing = timingOf(next);
    if (previous) {
      this.leaving.push({
        instance: previous.instance,
        from: new Map(previous.weights),
        weights: new Map(previous.weights),
        elapsed: 0,
        timing,
      });
    }
    for (const action of next.parts.values()) {
      action.reset();
      action.setEffectiveWeight(0);
      action.play();
    }
    this.gesture = { instance: next, peak, level: peak, weights: new Map() };
    return true;
  }

  /** 回覆講完：還在做的動作讓它做完，自己淡回 idle。 */
  stop(): void {}

  update(dt: number): void {
    const gesture = this.gesture;
    if (gesture) {
      const timing = timingOf(gesture.instance);
      const elapsed = this.timeOf(gesture.instance);
      const remaining = gesture.instance.duration - elapsed;
      const step = dt / timing.enter;
      gesture.level += Math.max(-step, Math.min(step, gesture.peak - gesture.level));
      for (const [part, action] of gesture.instance.parts) {
        const delay = timing.delays.get(part) ?? 0;
        // 軀幹先回、頭最後回：越晚開始的部位越晚回到 idle。
        const weight =
          gesture.level *
          ease((elapsed - delay) / timing.enter) *
          ease((remaining - (timing.last - delay)) / timing.ret);
        gesture.weights.set(part, weight);
        action.setEffectiveWeight(weight);
      }
      if (remaining <= 1e-6 && elapsed > 0) {
        this.release(gesture.instance);
        this.gesture = null;
      }
    }
    for (const item of this.leaving) {
      item.elapsed += dt;
      for (const [part, action] of item.instance.parts) {
        const delay = item.timing.delays.get(part) ?? 0;
        // 跟新動作同一條曲線、反過來：新的升多少，舊的就降多少。
        const weight = (item.from.get(part) ?? 0) * (1 - ease((item.elapsed - delay) / item.timing.enter));
        item.weights.set(part, weight);
        action.setEffectiveWeight(weight);
      }
    }
    this.leaving = this.leaving.filter((item) => {
      const done = item.elapsed >= item.timing.last + item.timing.enter;
      if (done) this.release(item.instance);
      return !done;
    });
    // 加起來超過 1 的部位（連換好幾個動作時）按比例壓回來。
    for (const part of PARTS) {
      const total = this.otherWeight(part);
      if (total > 1) {
        for (const [action, weight] of this.weightsOf(part)) action.setEffectiveWeight(weight / total);
      }
    }
    const idle = this.actions.get(IDLE_CLIP);
    if (idle) {
      for (const [part, action] of idle.parts) {
        if (action.isRunning()) action.setEffectiveWeight(Math.max(0, 1 - this.otherWeight(part)));
      }
    }
    this.mixer.update(dt);
  }

  private timeOf(instance: Instance): number {
    return instance.parts.values().next().value?.time ?? 0;
  }

  private returning(gesture: Gesture): boolean {
    const timing = timingOf(gesture.instance);
    const remaining = gesture.instance.duration - this.timeOf(gesture.instance);
    return remaining <= timing.ret + timing.last;
  }

  private release(instance: Instance): void {
    for (const action of instance.parts.values()) {
      action.setEffectiveWeight(0);
      action.stop();
    }
  }

  private weightsOf(part: Part): [THREE.AnimationAction, number][] {
    const out: [THREE.AnimationAction, number][] = [];
    const add = (instance: Instance, weights: Map<Part, number>) => {
      const action = instance.parts.get(part);
      if (action) out.push([action, weights.get(part) ?? 0]);
    };
    if (this.gesture) add(this.gesture.instance, this.gesture.weights);
    for (const item of this.leaving) add(item.instance, item.weights);
    return out;
  }

  /** 這個部位上，動作（正在做的＋淡出中的）的權重加總。 */
  private otherWeight(part: Part): number {
    return this.weightsOf(part).reduce((sum, [, weight]) => sum + weight, 0);
  }

  /** 這個動作沒在用的一份（本尊或複本）；都在用就多複製一份。 */
  private freeInstance(name: string, base: Instance): Instance {
    const busy = new Set<Instance>(this.leaving.map((item) => item.instance));
    if (this.gesture) busy.add(this.gesture.instance);
    const copies = this.copies.get(name) ?? [];
    const free = [base, ...copies].find((candidate) => !busy.has(candidate));
    if (free) return free;
    const tracks = [...base.parts.values()].flatMap((action) => action.getClip().tracks);
    const copy = this.instanceOf(name, new THREE.AnimationClip(name, base.duration, tracks).clone());
    this.copies.set(name, [...copies, copy]);
    return copy;
  }

  dispose(): void {
    this.disposed = true;
    // 飛在路上的 load() 會自己因為 disposed 而放棄（見該旗標的說明）；這裡清掉
    // map 只是不要再把它們當成「可以共用的進行中請求」交給新的呼叫者。
    this.pendingLoads.clear();
    this.mixer.stopAllAction();
    this.actions.clear();
    this.gesture = null;
    this.leaving = [];
    this.copies.clear();
  }
}
