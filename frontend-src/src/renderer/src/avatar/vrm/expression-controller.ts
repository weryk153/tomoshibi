// 情緒 preset 的淡入淡出，與口型的每幀寫入。改寫自 pixiv/ChatVRM (MIT) 的
// ExpressionController，去掉 three 依賴——這裡只認一個 setValue/has 的 sink，
// 讓它能在 node 裡測。
//
// 「清表情」就是把所有情緒淡到 0：VRM 的中性是全零，不用挑一個 neutral 蓋上去
// ——跟 Cubism 的 clearExpression() 同語意，Frieren 那個「0 號是哭臉」的坑在
// 這裡結構上不存在。

export interface ExpressionSink {
  has(name: string): boolean;
  setValue(name: string, weight: number): void;
  /** 這個表情宣告要蓋掉多少嘴型／眨眼。沒實作就當作 "none"（node 測試用得到）。 */
  overrideMouth?(name: string): string | undefined;
  overrideBlink?(name: string): string | undefined;
}

export const MOUTH_EXPRESSION = "aa";

// 情緒不推到滿，這是刻意的。VRM 1.0 的表情可以宣告 overrideMouth／overrideBlink：
// "blend" 模式下 three-vrm 算出來的倍率就是 1 −（該表情權重）
// （見 _calculateWeightMultipliers）。sample 模型的 happy 兩個都是 blend，所以
// 情緒一推到 1.0，倍率歸零——笑著講一整段話嘴巴完全不動，而且連眨眼都停掉。
// 留 0.3 的餘裕給嘴型和眨眼；單一 morph 的笑臉在 0.7 仍然清楚是在笑。
const EMOTION_MAX = 0.7;

// 倍率小到這個程度就不要硬補了：除出來會放大成一片抖動。
const MIN_MULTIPLIER = 0.05;

export class ExpressionController {
  private current: string | null = null;
  // 目前情緒要做多滿（0..1）。乘上 EMOTION_MAX 才是實際權重。
  private intensity = 1;
  private weights = new Map<string, number>();
  private mouth = 0;
  private warned = new Set<string>();
  private readonly sink: ExpressionSink;
  private readonly fadeSeconds: number;

  constructor(sink: ExpressionSink, fadeSeconds = 0.2) {
    this.sink = sink;
    this.fadeSeconds = fadeSeconds;
  }

  /**
   * 回 false 代表模型沒有這個表情；現狀不變。
   *
   * `intensity` 是「這個表情做多滿」，0..1，預設 1。同一個 happy 在 0.3 是抿嘴
   * 笑、在 1 是笑開，靠這個參數分層次——沒有它的話每次高興都是同一張臉。
   */
  setEmotion(name: string | null, intensity = 1): boolean {
    if (name !== null && !this.sink.has(name)) {
      if (!this.warned.has(name)) {
        this.warned.add(name);
        console.warn(`[VRM] expression "${name}" not found in model; ignoring`);
      }
      return false;
    }
    this.current = name;
    this.intensity = Math.max(0, Math.min(1, intensity));
    if (name !== null && !this.weights.has(name)) this.weights.set(name, 0);
    return true;
  }

  clear(): void {
    this.setEmotion(null);
  }

  setMouth(v: number): void {
    this.mouth = v;
  }

  /** 目前情緒把嘴型／眨眼壓掉多少之後，還剩幾成。0 代表完全被蓋掉。 */
  private multiplier(kind: "mouth" | "blink"): number {
    let overridden = 0;
    for (const [name, w] of this.weights) {
      const mode =
        kind === "mouth" ? this.sink.overrideMouth?.(name) : this.sink.overrideBlink?.(name);
      if (mode === "block") overridden += w > 0 ? 1 : 0;
      else if (mode === "blend") overridden += w;
    }
    return Math.max(0, 1 - overridden);
  }

  /** 眨眼是 renderer 直接寫進 VRM 的，倍率要在那邊補，所以往外露出來。 */
  blinkMultiplier(): number {
    return this.multiplier("blink");
  }

  /** 把 v 先除以倍率，抵銷 three-vrm 待會要乘的那一下。 */
  static compensate(v: number, multiplier: number): number {
    if (multiplier <= MIN_MULTIPLIER) return v;
    return Math.min(1, v / multiplier);
  }

  update(dt: number): void {
    const step = this.fadeSeconds > 0 ? dt / this.fadeSeconds : 1;
    for (const [name, w] of this.weights) {
      const target = name === this.current ? EMOTION_MAX * this.intensity : 0;
      const next = w < target ? Math.min(target, w + step) : Math.max(target, w - step);
      if (next !== w) {
        this.weights.set(name, next);
        this.sink.setValue(name, next);
      }
      if (next === 0 && target === 0) this.weights.delete(name);
    }
    if (this.sink.has(MOUTH_EXPRESSION)) {
      this.sink.setValue(
        MOUTH_EXPRESSION,
        ExpressionController.compensate(this.mouth, this.multiplier("mouth")),
      );
    }
  }
}
