// 自動眨眼。改寫自 pixiv/ChatVRM (MIT) 的 AutoBlink：閒 2–6 秒、閉 0.05 秒、
// 開 0.1 秒。純狀態機，rng 可注入。

const WAIT_MIN = 2;
const WAIT_RANGE = 4;
const CLOSE_SECONDS = 0.05;
const OPEN_SECONDS = 0.1;

export class AutoBlink {
  private phase: "wait" | "close" | "open" = "wait";
  private remaining: number;
  private readonly rng: () => number;

  constructor(rng: () => number = Math.random) {
    this.rng = rng;
    this.remaining = WAIT_MIN + this.rng() * WAIT_RANGE;
  }

  /** 回 blink 權重 0..1。 */
  update(dt: number): number {
    this.remaining -= dt;
    if (this.phase === "wait") {
      if (this.remaining > 0) return 0;
      this.phase = "close";
      this.remaining = CLOSE_SECONDS;
      return 0.01;
    }
    if (this.phase === "close") {
      if (this.remaining > 0) return 1 - Math.max(0, this.remaining / CLOSE_SECONDS);
      this.phase = "open";
      this.remaining = OPEN_SECONDS;
      return 1;
    }
    if (this.remaining > 0) return Math.max(0, this.remaining / OPEN_SECONDS);
    this.phase = "wait";
    this.remaining = WAIT_MIN + this.rng() * WAIT_RANGE;
    return 0;
  }
}
