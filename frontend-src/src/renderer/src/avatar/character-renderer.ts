// 角色 renderer 的共用介面。use-audio-task / audio-manager 只透過這個介面講話，
// 不知道底下是 Live2D 還是 VRM。
//
// 註冊表用模組變數而不是 React context：讀的人是 audio-manager（不是元件）和
// use-audio-task 裡「播放當下」的閉包——任務排進佇列時 renderer 可能還沒到或
// 已經換掉，所以必須在 canplaythrough 那一刻才讀，不能在 render 時抓。

/** 後端解析好的動作。Live2D 是 (group, index)，VRM 是 .vrma 檔名（不含副檔名）。 */
export type MotionRequest =
  | { group: string; index: number }
  | { clip: string };

export function isClipMotion(m: MotionRequest): m is { clip: string } {
  return "clip" in m;
}

export interface SpeakCues {
  /** Live2D：表情名或索引；VRM：expression preset／自訂名。 */
  expression?: string | number;
  motion?: MotionRequest;
}

export interface CharacterRenderer {
  /**
   * 一段音訊要開播。audio 已設好 src、已呼叫 play()。掛 lipsync、下表情、下動作。
   * firstOfResponse：這輪回覆的第一段——Live2D 只在這時起 Talk 動作。
   */
  beginSegment(
    audio: HTMLAudioElement,
    cues: SpeakCues,
    firstOfResponse: boolean,
  ): void;
  /** 打斷或整輪播完：停 lipsync、回 idle。 */
  stop(): void;
  /** AI 回到 IDLE：清表情回素顏。 */
  resetExpression(): void;
}

let active: CharacterRenderer | null = null;

/** 註冊為當前 renderer。回傳註銷函式；註銷只在自己仍是當前時才清，晚到的不會清掉別人。 */
export function registerRenderer(renderer: CharacterRenderer): () => void {
  active = renderer;
  return () => {
    if (active === renderer) active = null;
  };
}

export function getActiveRenderer(): CharacterRenderer | null {
  return active;
}
