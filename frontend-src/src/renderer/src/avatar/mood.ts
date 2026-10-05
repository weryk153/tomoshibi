// 她的心情（後端的 character-mood）怎麼變成空檔時的臉。
//
// 純函式加一個模組變數的小倉庫，沒有 import：node --test 直接載入。
// 淡掉的算法跟引擎（ai_character_engine.state.mood.effective_mood）一樣：
// 強度每過一個半衰期減半，跌破 MOOD_FLOOR 就當成沒有心情。後端送的是設下那一刻
// 的原始強度與時間，所以前端不必一直去問。

/** 跟引擎的 CompanionSettings.mood_floor 一樣。 */
export const MOOD_FLOOR = 0.15;
/** 空檔時多久重算一次淡到哪裡。 */
export const RESTING_REFRESH_MS = 10_000;

export interface CharacterMood {
  mood: string;
  /** 設下那一刻的強度 0..1，還沒淡。 */
  intensity: number;
  /** 設下的時間，epoch 秒。 */
  updatedAt: number;
  /** 半衰期，秒。 */
  halfLife: number;
}

export interface EffectiveMood {
  mood: string;
  intensity: number;
}

export interface Resting {
  /** Live2D：表情名或索引；VRM：preset 名。null＝清回素顏。 */
  expression: string | number | null;
  intensity: number;
}

const NEUTRAL: EffectiveMood = { mood: "neutral", intensity: 0 };

function finite(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function has(map: object, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(map, key);
}

/** 後端訊息 → CharacterMood；欄位不齊或不是數字就是 null（不動現在的臉）。 */
export function parseCharacterMood(raw: unknown): CharacterMood | null {
  if (!raw || typeof raw !== "object") return null;
  const message = raw as Record<string, unknown>;
  const { mood, intensity, updated_at: updatedAt, half_life: halfLife } = message;
  if (typeof mood !== "string" || !finite(intensity) || !finite(updatedAt) || !finite(halfLife)) {
    return null;
  }
  if (halfLife <= 0) return null;
  return { mood, intensity: Math.max(0, Math.min(1, intensity)), updatedAt, halfLife };
}

/** 她現在的心情。時間在未來（兩台機器的時鐘不一樣）當成沒過時間。 */
export function effectiveMood(mood: CharacterMood | null, nowSeconds: number): EffectiveMood {
  if (!mood || mood.mood === "neutral" || mood.intensity <= 0) return NEUTRAL;
  const elapsed = Math.max(0, nowSeconds - mood.updatedAt);
  const intensity = mood.intensity * 0.5 ** (elapsed / mood.halfLife);
  if (intensity < MOOD_FLOOR) return NEUTRAL;
  return { mood: mood.mood, intensity };
}

// 引擎的心情詞 → Tomoshibi 的表情關鍵字（emotionMap 的鍵）。
const KEYWORDS: Record<string, string | null> = {
  neutral: null,
  happy: "joy",
  sad: "sadness",
  angry: "anger",
  surprised: "surprise",
  embarrassed: "embarrassed",
  calm: "relaxed",
  worried: "sadness",
};
// 模型的 emotionMap 沒有那個關鍵字時，依序改找這些；都沒有就是沒有表情。
const FALLBACKS: Record<string, string[]> = {
  embarrassed: ["joy"],
  relaxed: ["neutral"],
};

export function moodToKeyword(mood: string): string | null {
  return has(KEYWORDS, mood) ? KEYWORDS[mood] : null;
}

/** 這個模型用哪個表情來表現這個心情；Live2D 的 0 號也是表情。 */
export function restingExpression(
  mood: string,
  emotionMap: Record<string, string | number> | undefined,
): string | number | null {
  const keyword = moodToKeyword(mood);
  if (keyword === null || !emotionMap) return null;
  for (const candidate of [keyword, ...(FALLBACKS[keyword] ?? [])]) {
    if (has(emotionMap, candidate)) return emotionMap[candidate];
  }
  return null;
}

/** 空檔時的臉：哪個表情、多濃。 */
export function restingFor(
  mood: CharacterMood | null,
  emotionMap: Record<string, string | number> | undefined,
  nowSeconds: number,
): Resting {
  const now = effectiveMood(mood, nowSeconds);
  const expression = restingExpression(now.mood, emotionMap);
  return expression === null ? { expression: null, intensity: 0 } : { expression, intensity: now.intensity };
}

// review 空檔重算：10 秒的 interval 不管有沒有變都呼叫 resetExpression()，會把
// 設定頁試播、Live2D 頭部點擊的隨機表情之類「使用者剛剛自己叫出來的臉」在
// 0～10 秒內蓋掉。真正需要整個重套（resetExpression）的只有「表情本身換了」
// ——跟 null 之間的切換也算換。同一個表情只是強度隨時間淡掉不算換，renderer
// 自己決定要不要悄悄更新濃淡（見 VRMRenderer.setRestingExpression；Live2D 沒有
// 濃淡，不會有動作）。
/**
 * 空檔重算時要不要整個重新套用（resetExpression）。previous 是上次「真的套用
 * 過」的值，null 代表這次效果掛載後還沒套用過（例如 renderer 剛註冊，還在補
 * 追進度）——這種情況一律要套一次。
 */
export function shouldApplyResting(previous: Resting | null, next: Resting): boolean {
  if (previous === null) return true;
  return previous.expression !== next.expression;
}

// 最新的心情。讀的人是 avatar.tsx 的空檔重算（不是元件 render），跟
// character-renderer.ts 的註冊表同一種做法。
let latest: CharacterMood | null = null;
const listeners = new Set<() => void>();

export function setCharacterMood(mood: CharacterMood | null): void {
  latest = mood;
  for (const listener of [...listeners]) listener();
}

export function getCharacterMood(): CharacterMood | null {
  return latest;
}

export function onCharacterMoodChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
