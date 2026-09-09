// 每幀用 audio.currentTime 查包絡 → 平滑 → 整形。只在 !paused && !ended 時讀：
// 換 src 時 currentTime 歸零、paused 變 true，舊段的包絡不會套到新段的前幾幀。
import {
  envelopeAt,
  envelopeFromDataUrl,
  FAKE_ENVELOPE,
  shapeMouth,
  type WavEnvelope,
} from "./wav-envelope.ts";

const SMOOTH_PER_SECOND = 20;

export class LipSync {
  private audio: HTMLAudioElement | null = null;
  private envelope: WavEnvelope | null = null;
  private smoothed = 0;

  begin(audio: HTMLAudioElement): void {
    this.audio = audio;
    const env = envelopeFromDataUrl(audio.src);
    if (!env) {
      console.warn("[VRM] could not parse WAV for lip sync; using constant mouth");
    }
    this.envelope = env ?? FAKE_ENVELOPE;
  }

  stop(): void {
    this.audio = null;
    this.envelope = null;
    this.smoothed = 0;
  }

  /** 回 0..1 的嘴型。 */
  update(dt: number): number {
    let target = 0;
    const a = this.audio;
    if (a && this.envelope && !a.paused && !a.ended) {
      target = shapeMouth(envelopeAt(this.envelope, a.currentTime));
    }
    this.smoothed += (target - this.smoothed) * Math.min(1, dt * SMOOTH_PER_SECOND);
    return this.smoothed;
  }
}
