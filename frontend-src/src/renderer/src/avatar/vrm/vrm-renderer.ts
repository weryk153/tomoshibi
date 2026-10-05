// frontend-src/src/renderer/src/avatar/vrm/vrm-renderer.ts
import type { VRM } from "@pixiv/three-vrm";
import type { CharacterRenderer, SpeakCues, PreviewMotionResult } from "../character-renderer.ts";
import { isClipMotion } from "../character-renderer.ts";
import { ExpressionController } from "./expression-controller.ts";
import { AutoBlink } from "./auto-blink.ts";
import { LipSync } from "./lip-sync.ts";
import { IDLE_CLIP, type MotionPlayer } from "./motion-player.ts";

export class VRMRenderer implements CharacterRenderer {
  private readonly vrm: VRM;
  private readonly motions: MotionPlayer;
  private readonly expressions: ExpressionController;
  private lip = new LipSync();
  private blink = new AutoBlink();
  private elapsed = 0;
  // 試播的世代號，見 previewMotion。只在那一個方法裡讀寫。
  private previewGeneration = 0;
  // 空檔時的臉：她的心情。見 CharacterRenderer.setRestingExpression。
  private resting: { name: string; intensity: number } | null = null;

  // 明確欄位指派而不是 constructor parameter property：node --experimental-strip-types
  // 只剝型別、不轉譯這個語法（見 frontend-node-test-constraints），這個檔案要能被
  // vrm-renderer.test.ts 用 node --test 載入就不能用那個寫法。行為不變。
  constructor(vrm: VRM, motions: MotionPlayer, expressions: ExpressionController) {
    this.vrm = vrm;
    this.motions = motions;
    this.expressions = expressions;
  }

  beginSegment(audio: HTMLAudioElement, cues: SpeakCues): void {
    this.lip.begin(audio);
    if (cues.expression !== undefined) {
      this.expressions.setEmotion(String(cues.expression), cues.intensity ?? 1);
    }
    if (cues.motion && isClipMotion(cues.motion)) {
      this.motions.playOnce(cues.motion.clip, cues.motion.intensity ?? 1);
    }
  }

  stop(): void {
    this.lip.stop();
    this.motions.stop();
  }

  setRestingExpression(expression: string | number | null, intensity: number): void {
    this.resting =
      expression === null || !(intensity > 0)
        ? null
        : { name: String(expression), intensity: Math.min(1, intensity) };
  }

  resetExpression(): void {
    // 權重是 EMOTION_MAX（0.7）× 強度，淡入沿用 0.2 秒（ExpressionController）。
    // 模型沒有這個表情時 setEmotion 回 false，那就清回素顏，不留著講話時的臉。
    if (this.resting && this.expressions.setEmotion(this.resting.name, this.resting.intensity)) {
      return;
    }
    this.expressions.clear();
  }

  /** 設定頁試播：套一個表情，強度固定拉滿——跟 handlePreview 一樣，試播不需要分層次。 */
  previewExpression(name: string): void {
    this.expressions.setEmotion(name, 1);
  }

  /**
   * 設定頁試播：播一次動作，強度固定拉滿。先 ensureLoaded 現拉一次——角色載入
   * 當下只預先讀了 motionMap 裡當時有的 clip（見 vrm-avatar.tsx），剛存檔、還
   * 沒試播過的 clip 這裡才會真的去要那個檔案。ensureLoaded 失敗（角色根本沒有
   * 這個 .vrma）就不播，回 false 讓 UI 顯示「這個角色沒有這個動作」。
   */
  async previewMotion(clip: string): Promise<PreviewMotionResult> {
    // ensureLoaded 可能是一次真的 .vrma 網路請求（見 MotionPlayer）。沒有這個
    // 世代號的話，先點的慢 clip 載完後會 playOnce 蓋掉後點的快 clip——使用者
    // 看到的是自己最後點的動作沒播、播的是前一個。每次呼叫先領號，await 回來
    // 如果號碼已經不是最新的就放棄，不播也不回報錯誤。
    const generation = this.previewGeneration + 1;
    this.previewGeneration = generation;
    const loaded = await this.motions.ensureLoaded(clip);
    if (generation !== this.previewGeneration) return 'superseded';
    if (!loaded) return 'missing';
    return this.motions.playOnce(clip, 1) ? 'played' : 'missing';
  }

  /** 存檔後背景預先載入，不播放——見 CharacterRenderer.ensureMotionLoaded 的說明。 */
  async ensureMotionLoaded(clip: string): Promise<boolean> {
    return this.motions.ensureLoaded(clip);
  }

  /** 每幀。lookTarget 為 null 時不動視線。 */
  update(dt: number): void {
    this.elapsed += dt;
    this.expressions.setMouth(this.lip.update(dt));
    this.expressions.update(dt);
    // 眨眼也會被 overrideBlink 壓掉（sample 模型的 happy 就是 blend），所以跟嘴型
    // 一樣要先除掉待會 three-vrm 會乘的那個倍率，否則笑的時候等於不眨眼。
    this.vrm.expressionManager?.setValue(
      "blink",
      ExpressionController.compensate(this.blink.update(dt), this.expressions.blinkMultiplier()),
    );
    if (!this.motions.hasClip(IDLE_CLIP)) {
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
