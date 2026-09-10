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

  constructor(private readonly vrm: VRM) {
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
    this.mixer.stopAllAction();
    this.actions.clear();
    this.current = null;
  }
}
