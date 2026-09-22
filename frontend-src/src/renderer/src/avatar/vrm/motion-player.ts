// frontend-src/src/renderer/src/avatar/vrm/motion-player.ts
// .vrma 動畫：idle 迴圈 + LLM 觸發的 one-shot，之間 0.3 秒 crossfade。
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { VRM } from "@pixiv/three-vrm";
import {
  VRMAnimationLoaderPlugin,
  createVRMAnimationClip,
  type VRMAnimation,
} from "@pixiv/three-vrm-animation";

export const IDLE_CLIP = "idle";
const FADE = 0.3;

export class MotionPlayer {
  private mixer: THREE.AnimationMixer;
  private actions = new Map<string, THREE.AnimationAction>();
  private current: THREE.AnimationAction | null = null;
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
    this.mixer.addEventListener("finished", () => {
      // one-shot 播完回 idle。
      this.playIdle();
    });
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
      const clip = createVRMAnimationClip(anims[0], this.vrm);
      const action = this.mixer.clipAction(clip);
      if (name === IDLE_CLIP) {
        action.setLoop(THREE.LoopRepeat, Number.POSITIVE_INFINITY);
      } else {
        action.setLoop(THREE.LoopOnce, 1);
        action.clampWhenFinished = true;
      }
      this.actions.set(name, action);
      return true;
    } catch (e) {
      console.warn(`[VRM] failed to load motion ${name}:`, e);
      return false;
    }
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

  private crossfadeTo(next: THREE.AnimationAction, weight = 1): void {
    // 直接設 .weight 而不是 setEffectiveWeight()——後者會順手 stopFading()，
    // 把下一行的 fadeIn 當場取消掉，動作變成瞬間切換。three.js 每幀算的是
    // weight × 淡入插值，所以這樣設完再 fadeIn，兩者會正確相乘。
    next.reset();
    next.weight = weight;
    next.fadeIn(FADE).play();
    if (this.current && this.current !== next) this.current.fadeOut(FADE);
    this.current = next;
  }

  playIdle(): void {
    const idle = this.actions.get(IDLE_CLIP);
    if (!idle) {
      if (this.current) this.current.fadeOut(FADE);
      this.current = null;
      return;
    }
    if (this.current === idle) return;
    this.crossfadeTo(idle);
  }

  /**
   * `intensity` 是「這個動作做多大」，0..1，預設 1。用 setEffectiveWeight 調——
   * 權重不滿時 idle 會從底下透出來，所以 0.4 的揮手就是小幅度的揮手，而不是另外
   * 準備一個小幅度的片段。
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
    this.crossfadeTo(action, Math.max(0, Math.min(1, intensity)));
    return true;
  }

  stop(): void {
    this.playIdle();
  }

  update(dt: number): void {
    this.mixer.update(dt);
  }

  dispose(): void {
    this.disposed = true;
    // 飛在路上的 load() 會自己因為 disposed 而放棄（見該旗標的說明）；這裡清掉
    // map 只是不要再把它們當成「可以共用的進行中請求」交給新的呼叫者。
    this.pendingLoads.clear();
    this.mixer.stopAllAction();
    this.actions.clear();
    this.current = null;
  }
}
