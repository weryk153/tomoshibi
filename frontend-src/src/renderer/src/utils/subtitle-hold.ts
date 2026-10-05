/**
 * Which subtitle a spoken segment puts on the canvas — or `null` to leave the
 * current one alone.
 *
 * The backend flags a segment `keep_subtitle` when it is nothing but laughter
 * (「哈↗哈↘哈↗！」 split off by the sentence divider). Its audio still plays and
 * the chat bubble still gets it; only the canvas subtitle keeps her previous
 * line, so a 「哈哈哈！」 doesn't flash up between two real sentences.
 *
 * "Previous line" means a line she spoke. If what is on screen is something
 * else — the thinking indicator, a notice, or nothing because the last turn
 * ended — holding it would leave 「思考中…」 up while she audibly laughs, so the
 * laugh is shown after all. `lastSpoken` is the last text a segment put up;
 * when the screen no longer shows it, something else took over.
 *
 * Extracted from use-audio-task so it is testable under plain `node --test`.
 */
export function nextSpeechSubtitle(options: {
  hasAudio: boolean
  visibleText: string
  keepSubtitle: boolean
  current: string
  lastSpoken: string | null
}): string | null {
  const {
    hasAudio, visibleText, keepSubtitle, current, lastSpoken,
  } = options;
  // Silent segments never touched the subtitle; that stays as it was.
  if (!hasAudio) return null;
  if (keepSubtitle && current !== '' && current === lastSpoken) return null;
  return visibleText;
}
