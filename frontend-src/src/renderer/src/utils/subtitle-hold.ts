/**
 * What the canvas subtitle shows. `spoken` is the bilingual-subtitle line: the
 * sentence she actually voices (after voice translation), drawn above `text`.
 * `null` when the character's 雙語字幕 switch is off, the sentence was not
 * translated, or both lines read the same — then only `text` is shown.
 */
export interface SubtitleLine {
  text: string
  spoken: string | null
}

/**
 * Which subtitle a spoken segment puts on the canvas — or `null` to leave the
 * current one alone.
 *
 * The backend flags a segment `keep_subtitle` when it is nothing but laughter
 * (「哈↗哈↘哈↗！」 split off by the sentence divider). Its audio still plays and
 * the chat bubble still gets it; only the canvas subtitle keeps her previous
 * line, so a 「哈哈哈！」 doesn't flash up between two real sentences. Holding
 * keeps both lines of a bilingual subtitle.
 *
 * "Previous line" means a line she spoke. If what is on screen is something
 * else — the thinking indicator, a notice, or nothing because the last turn
 * ended — holding it would leave 「思考中…」 up while she audibly laughs, so the
 * laugh is shown after all. `lastSpoken` is the last text a segment put up;
 * when the screen no longer shows it, something else took over.
 *
 * `spokenText` is the payload's `spoken_text`, present only when the character
 * has bilingual subtitles on.
 *
 * Extracted from use-audio-task so it is testable under plain `node --test`.
 */
export function nextSpeechSubtitle(options: {
  hasAudio: boolean
  visibleText: string
  spokenText?: string | null
  keepSubtitle: boolean
  current: string
  lastSpoken: string | null
}): SubtitleLine | null {
  const {
    hasAudio, visibleText, spokenText, keepSubtitle, current, lastSpoken,
  } = options;
  // Silent segments never touched the subtitle; that stays as it was.
  if (!hasAudio) return null;
  if (keepSubtitle && current !== '' && current === lastSpoken) return null;
  const spoken = spokenText?.trim() ?? '';
  return {
    text: visibleText,
    spoken: spoken !== '' && spoken !== visibleText.trim() ? spoken : null,
  };
}

/**
 * Put new text on the subtitle by any path other than a spoken segment (a
 * notice, a scheduled clear, the end of the conversation). The spoken line
 * belongs to the text it was sent with, so it goes when the text changes; an
 * unchanged text keeps the same object so React skips the re-render.
 */
export function replaceSubtitleText(line: SubtitleLine, text: string): SubtitleLine {
  if (line.text === text) return line;
  return { text, spoken: null };
}
