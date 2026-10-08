// frontend-src/src/renderer/src/avatar/vrm/motion-player.ts
// .vrma 動畫：idle 迴圈 + LLM 觸發的 one-shot。
//
// idle 一直在播、從不重來；動作疊在上面，每幀的權重由這裡算（不用 three.js
// 的 fadeIn/fadeOut）：動作淡入 FADE_IN 秒，結束前 RETURN_FADE 秒開始淡回，播
// 完時剛好回到 idle。idle 的權重永遠是 1 減掉動作的，所以強度 0.5 的揮手是
// 「一半揮手、一半 idle」，不會混進 T-pose；回覆講完也不打斷還在做的動作。
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { VRM } from "@pixiv/three-vrm";
import {
  VRMAnimationLoaderPlugin,
  createVRMAnimationClip,
  type VRMAnimation,
} from "@pixiv/three-vrm-animation";

export const IDLE_CLIP = "idle";
// 動作淡入的時間；換下一個動作時，舊的也用這麼久淡出。
const FADE_IN = 0.3;
// 動作結束前多久開始淡回 idle。太短看起來像彈回去。
const RETURN_FADE = 0.7;

// peak 是要的強度，level 是這一幀的強度（往 peak 慢慢靠，強度改了也不會跳）。
type Gesture = {
  name: string;
  action: THREE.AnimationAction;
  peak: number;
  level: number;
  weight: number;
};
type Leaving = { action: THREE.AnimationAction; weight: number; rate: number };

export class MotionPlayer {
  private mixer: THREE.AnimationMixer;
  private actions = new Map<string, THREE.AnimationAction>();
  private gesture: Gesture | null = null;
  private leaving: Leaving[] = [];
  // 同一個動作還在淡出時又要做一次，就用它的複本淡入：同一個 action 不能
  // 同時淡出又從頭開始（reset 會讓它一幀之內跳回第一格、權重歸零）。
  private copies = new Map<string, THREE.AnimationAction[]>();
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
    const action = this.mixer.clipAction(clip);
    if (name === IDLE_CLIP) {
      action.setLoop(THREE.LoopRepeat, Number.POSITIVE_INFINITY);
    } else {
      action.setLoop(THREE.LoopOnce, 1);
      action.clampWhenFinished = true;
    }
    this.actions.set(name, action);
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
    if (idle && !idle.isRunning()) {
      idle.setEffectiveWeight(1 - this.gestureWeight());
      idle.play();
    }
  }

  /**
   * `intensity` 是「這個動作做多大」，0..1，預設 1：權重不滿時 idle 從底下補
   * 上，所以 0.4 的揮手就是小幅度的揮手，而不是另外準備一個小幅度的片段。
   */
  playOnce(name: string, intensity = 1): boolean {
    const action = this.actions.get(name);
    if (!action) {
      console.warn(`[VRM] motion clip "${name}" not loaded; staying idle`);
      return false;
    }
    // 太小的話動作幾乎看不見，卻仍然佔著「正在播動作」的狀態擋住 idle，
    // 看起來就只是僵住。低於這個值直接當作沒有這個動作。
    if (intensity < 0.05) return false;
    const peak = Math.max(0, Math.min(1, intensity));
    const previous = this.gesture;
    if (previous && previous.name === name && !this.returning(previous)) {
      // 還在做同一個動作：接著做，只換強度（慢慢換）。
      previous.peak = peak;
      return true;
    }
    if (previous) this.letGo(previous.action, previous.weight);
    const next = this.freeAction(name, action);
    next.reset();
    next.setEffectiveWeight(0);
    next.play();
    this.gesture = { name, action: next, peak, level: peak, weight: 0 };
    return true;
  }

  private returning(gesture: Gesture): boolean {
    const duration = gesture.action.getClip().duration;
    return duration - gesture.action.time <= Math.min(RETURN_FADE, duration / 2);
  }

  private letGo(action: THREE.AnimationAction, weight: number): void {
    if (weight > 0) {
      this.leaving.push({ action, weight, rate: weight / FADE_IN });
    } else {
      action.setEffectiveWeight(0);
      action.stop();
    }
  }

  /** 這個動作沒在用的一份（本尊或複本）；都在用就多複製一份。 */
  private freeAction(name: string, base: THREE.AnimationAction): THREE.AnimationAction {
    const busy = new Set<THREE.AnimationAction>(this.leaving.map((item) => item.action));
    if (this.gesture) busy.add(this.gesture.action);
    const copies = this.copies.get(name) ?? [];
    const free = [base, ...copies].find((candidate) => !busy.has(candidate));
    if (free) return free;
    const copy = this.mixer.clipAction(base.getClip().clone());
    copy.setLoop(THREE.LoopOnce, 1);
    copy.clampWhenFinished = true;
    this.copies.set(name, [...copies, copy]);
    return copy;
  }

  /** 回覆講完：還在做的動作讓它做完，自己淡回 idle。 */
  stop(): void {}

  update(dt: number): void {
    const gesture = this.gesture;
    if (gesture) {
      const duration = gesture.action.getClip().duration;
      const fadeIn = Math.min(FADE_IN, duration / 2);
      const fadeOut = Math.min(RETURN_FADE, duration / 2);
      const elapsed = gesture.action.time;
      const remaining = duration - elapsed;
      const step = dt / FADE_IN;
      gesture.level += Math.max(-step, Math.min(step, gesture.peak - gesture.level));
      gesture.weight =
        gesture.level *
        Math.min(1, fadeIn > 0 ? elapsed / fadeIn : 1) *
        Math.max(0, Math.min(1, fadeOut > 0 ? remaining / fadeOut : 0));
      gesture.action.setEffectiveWeight(gesture.weight);
      if (remaining <= 1e-6 && elapsed > 0) {
        gesture.action.setEffectiveWeight(0);
        gesture.action.stop();
        this.gesture = null;
      }
    }
    for (const item of this.leaving) {
      item.weight = Math.max(0, item.weight - item.rate * dt);
      item.action.setEffectiveWeight(item.weight);
      if (item.weight === 0) item.action.stop();
    }
    this.leaving = this.leaving.filter((item) => item.weight > 0);
    const idle = this.actions.get(IDLE_CLIP);
    if (idle && idle.isRunning()) idle.setEffectiveWeight(1 - this.gestureWeight());
    this.mixer.update(dt);
  }

  private gestureWeight(): number {
    let total = this.gesture?.weight ?? 0;
    for (const item of this.leaving) total += item.weight;
    return Math.min(1, total);
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
