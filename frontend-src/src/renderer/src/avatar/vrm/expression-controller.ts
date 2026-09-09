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
}

export const MOUTH_EXPRESSION = "aa";

export class ExpressionController {
  private current: string | null = null;
  private weights = new Map<string, number>();
  private mouth = 0;
  private warned = new Set<string>();
  private readonly sink: ExpressionSink;
  private readonly fadeSeconds: number;

  constructor(sink: ExpressionSink, fadeSeconds = 0.2) {
    this.sink = sink;
    this.fadeSeconds = fadeSeconds;
  }

  /** 回 false 代表模型沒有這個表情；現狀不變。 */
  setEmotion(name: string | null): boolean {
    if (name !== null && !this.sink.has(name)) {
      if (!this.warned.has(name)) {
        this.warned.add(name);
        console.warn(`[VRM] expression "${name}" not found in model; ignoring`);
      }
      return false;
    }
    this.current = name;
    if (name !== null && !this.weights.has(name)) this.weights.set(name, 0);
    return true;
  }

  clear(): void {
    this.setEmotion(null);
  }

  setMouth(v: number): void {
    this.mouth = v;
  }

  update(dt: number): void {
    const step = this.fadeSeconds > 0 ? dt / this.fadeSeconds : 1;
    for (const [name, w] of this.weights) {
      const target = name === this.current ? 1 : 0;
      const next = w < target ? Math.min(target, w + step) : Math.max(target, w - step);
      if (next !== w) {
        this.weights.set(name, next);
        this.sink.setValue(name, next);
      }
      if (next === 0 && target === 0) this.weights.delete(name);
    }
    if (this.sink.has(MOUTH_EXPRESSION)) {
      this.sink.setValue(MOUTH_EXPRESSION, this.mouth);
    }
  }
}
