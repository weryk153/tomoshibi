/**
 * The rule that decides whether a scheduled subtitle clear may still fire.
 *
 * Transient subtitles (system notices, a VAD misfire) schedule their own
 * removal. Between scheduling and firing the character may have started
 * speaking — and a timer that clears unconditionally would wipe her line
 * mid-sentence, leaving the canvas blank while audio plays. So a pending clear
 * only applies if the text on screen is still the one that scheduled it.
 *
 * Extracted from the provider so the rule is testable: the provider is a React
 * context and the test runner here is plain `node --test` over .ts files.
 */
export function resolveAutoClear(current: string, scheduledFor: string): string {
  return current === scheduledFor ? '' : current;
}

/**
 * The rule that decides whether the end of a conversation clears the subtitle.
 *
 * Each spoken chunk pushes its line onto the canvas, but nothing used to take
 * the last one down — so after the character finished speaking her final
 * sentence stayed on screen indefinitely, until some later turn happened to
 * overwrite it. Subtitles are the text half of speech; when the audio is gone
 * the text should go with it.
 *
 * `conversation-chain-end` is queued behind the audio, so by the time it fires
 * something else may already own the subtitle — a character-switch notice, a
 * "new conversation" toast. Those schedule their own removal and are not ours
 * to wipe, so pass them in `keep` and they survive.
 */
export function resolveConversationEndClear(
  current: string,
  keep: ReadonlySet<string> = new Set(),
): string {
  return keep.has(current) ? current : '';
}
