// 角色 renderer 的共用介面。use-audio-task / audio-manager 只透過這個介面講話，
// 不知道底下是 Live2D 還是 VRM。
//
// 註冊表用模組變數而不是 React context：讀的人是 audio-manager（不是元件）和
// use-audio-task 裡「播放當下」的閉包——任務排進佇列時 renderer 可能還沒到或
// 已經換掉，所以必須在 canplaythrough 那一刻才讀，不能在 render 時抓。

/** 後端解析好的動作。Live2D 是 (group, index)，VRM 是 .vrma 檔名（不含副檔名）。 */
// intensity 是「這個動作做多大」，0..1，沒給＝1。後端只在不是 1 的時候才附上
// 這個鍵（見 avatar_model.extract_motions）。Live2D 的動作沒有權重的概念，
// 那條路徑會忽略它。
export type MotionRequest =
  | { group: string; index: number; intensity?: number }
  | { clip: string; intensity?: number };

export function isClipMotion(m: MotionRequest): m is { clip: string } {
  return "clip" in m;
}

export interface SpeakCues {
  /** Live2D：表情名或索引；VRM：expression preset／自訂名。 */
  expression?: string | number;
  /** 表情強度 0..1，沒給＝1。Live2D 的表情是獨立檔案，那邊會忽略。 */
  intensity?: number;
  motion?: MotionRequest;
}

/**
 * 試播的結果。以前是 boolean，但 false 同時代表兩件完全不同的事：「這個角色
 * 沒有這個動作檔」（要告訴使用者）與「載入還沒回來就被下一次試播取代了」
 * （不該告訴使用者，那是他自己點的）。合在一起會讓連點兩個動作時彈出
 * 「這個角色沒有這個動作」的假錯誤，所以拆成三態。
 */
export type PreviewMotionResult = 'played' | 'missing' | 'superseded';

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
  /**
   * 空檔時的臉（她的心情）。expression 是這個模型的表情（Live2D 名字或索引、
   * VRM preset，見 avatar/mood.ts 的 restingFor），null＝沒有心情；intensity 是
   * 淡掉之後的強度 0..1。基本上只記下來，resetExpression() 才套用；唯一的例外是
   * VRM 目前顯示的臉就是這個表情時，會順手把淡掉後的濃淡推進去（見 VRMRenderer）。
   */
  setRestingExpression(expression: string | number | null, intensity: number): void;
  /**
   * 現在套表情有沒有用（模型載完了沒）。avatar.tsx 的空檔重算在還沒就緒時不套、
   * 也不記成「套過了」，等下一次再試。沒實作＝註冊時就已就緒（VRM 載完才註冊）。
   * Live2D 是一掛上就註冊、模型之後才非同步載完，所以要這個。
   */
  isReady?(): boolean;
  /** AI 回到 IDLE：回到 resting 表情；沒有 resting 就清回素顏。 */
  resetExpression(): void;
  /** 設定頁試播：套一個表情（VRM 是 preset／自訂名）。沒實作＝這個 renderer 不支援試播。 */
  previewExpression?(name: string): void;
  /**
   * 設定頁試播：播一次動作。VRM 可能要現拉還沒載入過的 .vrma（角色載入當下只
   * 預先讀了 motionMap 裡當時有的 clip），所以是非同步；回傳值代表「這個動作
   * 真的有播成功」——false 給 UI 顯示「這個角色沒有這個動作」，不是靜靜地
   * 什麼都不做。
   */
  previewMotion?(clip: string): void | Promise<PreviewMotionResult>;
  /**
   * 存檔成功後，對每個新指到 motionMap 的 clip 呼叫，背景預先載入、不播放——
   * 讓 LLM 接下來能立刻觸發剛存的關鍵字，不用等使用者自己先按一次試播。
   * 沒實作＝這個 renderer 不需要預先載入（例如 Live2D 動作本來就都在
   * model3.json 裡，載入模型時已經全部讀完）。
   */
  ensureMotionLoaded?(clip: string): Promise<boolean>;
}

let active: CharacterRenderer | null = null;
// fix round 1：avatar.tsx 進 IDLE 時若 renderer 還沒註冊好（VRM 是 lazy import，
// Live2D 畫布也要等載入），空檔的臉本來要等到下一次 10 秒的 tick 才補上。訂閱這個
// 就能在 renderer 一註冊好馬上補套一次，不用乾等。
const registrationListeners = new Set<() => void>();

/** 註冊為當前 renderer。回傳註銷函式；註銷只在自己仍是當前時才清，晚到的不會清掉別人。 */
export function registerRenderer(renderer: CharacterRenderer): () => void {
  active = renderer;
  for (const listener of [...registrationListeners]) listener();
  return () => {
    if (active === renderer) active = null;
  };
}

export function getActiveRenderer(): CharacterRenderer | null {
  return active;
}

/** 有新 renderer 註冊時收到通知（不含註銷）。回傳取消訂閱函式。 */
export function onRendererRegistered(listener: () => void): () => void {
  registrationListeners.add(listener);
  return () => {
    registrationListeners.delete(listener);
  };
}
