// frontend-src/src/renderer/src/avatar/vrm/vrm-renderer.ts
import type { VRM } from "@pixiv/three-vrm";
import type { CharacterRenderer, SpeakCues } from "../character-renderer.ts";
import { isClipMotion } from "../character-renderer.ts";
import { ExpressionController } from "./expression-controller.ts";
import { AutoBlink } from "./auto-blink.ts";
import { LipSync } from "./lip-sync.ts";
import type { MotionPlayer } from "./motion-player.ts";

export class VRMRenderer implements CharacterRenderer {
  private lip = new LipSync();
  private blink = new AutoBlink();
  private elapsed = 0;

  constructor(
    private readonly vrm: VRM,
    private readonly motions: MotionPlayer,
    private readonly expressions: ExpressionController,
  ) {}

  beginSegment(audio: HTMLAudioElement, cues: SpeakCues): void {
    this.lip.begin(audio);
    if (cues.expression !== undefined) {
      this.expressions.setEmotion(String(cues.expression));
    }
    if (cues.motion && isClipMotion(cues.motion)) {
      this.motions.playOnce(cues.motion.clip);
    }
  }

  stop(): void {
    this.lip.stop();
    this.motions.stop();
  }

  resetExpression(): void {
    this.expressions.clear();
  }

  /** 每幀。lookTarget 為 null 時不動視線。 */
  update(dt: number): void {
    this.elapsed += dt;
    this.expressions.setMouth(this.lip.update(dt));
    this.expressions.update(dt);
    this.vrm.expressionManager?.setValue("blink", this.blink.update(dt));
    if (!this.motions.hasClip("idle")) {
      // 沒有 idle 動畫時的程序式微擺，免得像人偶。
      const spine = this.vrm.humanoid?.getNormalizedBoneNode("spine");
      const chest = this.vrm.humanoid?.getNormalizedBoneNode("chest");
      if (spine) spine.rotation.z = Math.sin(this.elapsed * 0.8) * 0.01;
      if (chest) chest.rotation.x = Math.sin(this.elapsed * 1.6) * 0.01;
    }
    this.motions.update(dt);
    this.vrm.update(dt);
  }
}
