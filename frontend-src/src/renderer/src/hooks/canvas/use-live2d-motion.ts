import { useCallback } from 'react';
import { InvalidMotionQueueEntryHandleValue } from '@framework/motion/cubismmotionqueuemanager';

/**
 * A single LLM-triggered body motion, already resolved by the backend to a
 * concrete Live2D motion group + index (mirrors expression resolution).
 */
export interface MotionRequest {
  group: string;
  index: number;
}

/**
 * Play a body motion on the Live2D model.
 * @param motion - Motion group + index to play
 * @param lappAdapter - LAppAdapter instance
 * @param logMessage - Optional message to log on success
 */
export function playLive2DMotion(
  motion: MotionRequest,
  lappAdapter: any,
  logMessage?: string,
): void {
  // 不要寫 `!motion.group`。mao_pro 的六個動作全部住在**無名群組**裡，group
  // 就是空字串——而 `!''` 是 true，那樣寫會讓它們一個都播不出來，而且不會有
  // 任何錯誤訊息。無名群組是合法的：既有的 tap 路徑就是用 `tapMotions: {"": 1}`。
  if (!lappAdapter || !motion || typeof motion.group !== 'string') {
    return;
  }

  try {
    // PriorityForce (3): `reserveMotion` only accepts a request whose priority
    // is strictly greater than what is currently playing/reserved. The Talk
    // motion that plays during speech uses PriorityNormal (2), so anything
    // lower or equal would silently never play while the character is
    // talking -- exactly when an LLM-triggered motion is wanted.
    const handle = lappAdapter.startMotion(motion.group, motion.index, 3);

    // `startMotion` returns InvalidMotionQueueEntryHandleValue (-1) both for
    // a genuine failure (unknown group name or out-of-range index -- the
    // underlying model settings lookup returns an empty file name rather
    // than throwing) and, far more commonly, whenever the motion file is not
    // already cached: in that case it kicks off an async fetch and starts
    // the motion later, still returning -1 synchronously here. So a -1
    // return is not a reliable "it never played" signal -- just log it.
    if (handle === InvalidMotionQueueEntryHandleValue) {
      console.warn(
        `startMotion returned an invalid handle for group "${motion.group}" index ${motion.index} (may be a genuine failure, or just an in-flight async fetch)`,
      );
    } else if (logMessage) {
      console.log(logMessage);
    }
  } catch (error) {
    console.error('Failed to play motion:', error);
  }
}

/**
 * Custom hook for handling Live2D model body motions triggered by the LLM.
 * Structured after `use-live2d-expression.ts`.
 */
export const useLive2DMotion = () => {
  const playMotion = useCallback(playLive2DMotion, []);

  return {
    playMotion,
  };
};
