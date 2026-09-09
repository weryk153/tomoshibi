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

  private crossfadeTo(next: THREE.AnimationAction): void {
    next.reset().fadeIn(FADE).play();
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

  playOnce(name: string): boolean {
    const action = this.actions.get(name);
    if (!action) {
      console.warn(`[VRM] motion clip "${name}" not loaded; staying idle`);
      return false;
    }
    this.crossfadeTo(action);
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
