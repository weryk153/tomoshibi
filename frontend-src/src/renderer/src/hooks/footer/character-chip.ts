// 底部列角色膠囊的那一格字：空閒時是她的心情，忙的時候是她在做什麼。
//
// 純函式，只 import mood.ts（它本身也沒有 import），node --test 直接載入。
// aiState 用字串而不是 AiStateEnum：那個 enum 在 ai-state-context.tsx 裡，
// 一 import 就把 React 拖進來，node 測試跑不動。

import { MOOD_FLOOR } from '../../avatar/mood.ts';

/** 引擎會送的八個心情詞；i18n 的 key 是 mood.<word>。 */
export const MOOD_WORDS = [
  'neutral',
  'happy',
  'sad',
  'angry',
  'surprised',
  'embarrassed',
  'calm',
  'worried',
] as const;

export type MoodWord = (typeof MOOD_WORDS)[number];

/**
 * 圓點的顏色族。muted＝次文字灰、accent＝主色粉、accent2＝副色青、
 * accentSoft＝粉的淺階、danger＝紅、busy＝她在忙（圓點跳動）。
 */
export type ChipTone = 'muted' | 'accent' | 'accent2' | 'accentSoft' | 'danger' | 'busy';

const MOOD_TONE: Record<MoodWord, ChipTone> = {
  neutral: 'muted',
  calm: 'muted',
  happy: 'accent',
  surprised: 'accent',
  angry: 'danger',
  sad: 'accent2',
  worried: 'accent2',
  embarrassed: 'accentSoft',
};

function isMoodWord(word: string): word is MoodWord {
  return (MOOD_WORDS as readonly string[]).includes(word);
}

export interface ChipLabelInput {
  aiState: string;
  mood: string;
  /** 已經淡過的強度（effectiveMood 的結果）。 */
  intensity: number;
  t: (key: string) => string;
}

export interface ChipLabel {
  text: string;
  tone: ChipTone;
}

export function chipLabel({ aiState, mood, intensity, t }: ChipLabelInput): ChipLabel {
  // 不是空閒就說她在做什麼——思考／說話、聆聽、載入⋯⋯這時候心情不是重點，
  // 而且這顆膠囊接手了原本狀態徽章的 aria-live，讀螢幕要聽得到狀態。
  // waiting 例外、當成空閒：那是「使用者在打字」，use-footer 每按一個鍵就設
  // 一次、2 秒後回 idle，跟著換字的話打字時膠囊會一直閃（aria-live 也會一直念）。
  if (aiState !== 'idle' && aiState !== 'waiting') {
    return { text: t(`aiState.${aiState}`), tone: 'busy' };
  }
  // 淡到門檻以下、或引擎之後多了這裡不認得的詞，都當成沒有心情。
  const word: MoodWord = intensity >= MOOD_FLOOR && isMoodWord(mood) ? mood : 'neutral';
  return { text: t(`mood.${word}`), tone: MOOD_TONE[word] };
}
