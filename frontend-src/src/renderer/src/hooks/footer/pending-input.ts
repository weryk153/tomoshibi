/**
 * Queue for text typed while she is speaking.
 *
 * Pressing send during `thinking-speaking` must not interrupt her (that's
 * what the dedicated interrupt button is for). Instead the text is held here
 * and flushed as one combined `text-input` once she settles back to `idle`.
 *
 * Kept as a plain, side-effect-free module (no React, no WebSocket) so the
 * queueing/joining/flush-timing rules can be unit tested without a DOM or a
 * mocked context. The hook in `use-text-input.tsx` owns the mutable
 * ref/state and the actual `sendMessage` call.
 */

export interface PendingInputState {
  readonly queue: readonly string[];
}

export const EMPTY_PENDING_INPUT: PendingInputState = { queue: [] };

/** Add one message to the queue. Blank/whitespace-only text is dropped. */
export function enqueuePendingInput(state: PendingInputState, text: string): PendingInputState {
  const trimmed = text.trim();
  if (!trimmed) return state;
  return { queue: [...state.queue, trimmed] };
}

export function hasPendingInput(state: PendingInputState): boolean {
  return state.queue.length > 0;
}

/**
 * Combine everything queued into the single `text-input` that gets sent.
 * Joined by newlines, in the order typed — simpler and avoids racing turns
 * compared to sending each queued message as its own back-to-back turn.
 */
export function joinPendingInput(state: PendingInputState): string {
  return state.queue.join('\n');
}

export function clearPendingInput(): PendingInputState {
  return EMPTY_PENDING_INPUT;
}

/**
 * What to actually send for an immediate (non-queued) send, given whatever
 * is already queued from while she was speaking.
 *
 * Needed for: user types while she's speaking (queued) → user presses the
 * interrupt button → before the queue has a chance to auto-flush, the user
 * sends another message. That new message is sent immediately (state is no
 * longer `thinking-speaking`), but the older queued text must go out ahead
 * of it, not after — chat history already shows the older message first.
 */
export function mergeQueuedWithImmediate(state: PendingInputState, text: string): string {
  if (!hasPendingInput(state)) return text;
  return `${joinPendingInput(state)}\n${text}`;
}

/** Send now, or hold it for when she's done talking? */
export function shouldQueueInsteadOfSending(aiState: string): boolean {
  return aiState === 'thinking-speaking';
}

/**
 * Whether reaching `nextAiState` is the signal to automatically flush the
 * queue.
 *
 * Deliberately narrow: only a genuine return to `idle` (normally
 * conversation-chain-end) counts. `interrupted` is NOT included here on
 * purpose, for two reasons:
 *  - VAD's own interrupt-on-speech-detected passes through `interrupted` on
 *    its way to `listening`; flushing there would race the voice turn that
 *    is about to start.
 *  - An explicit interrupt-button press is a distinct user action ("cut her
 *    off now") from "she finished talking" — it gets its own direct flush
 *    call (see the hook) right after `interrupt()`, rather than being
 *    inferred from the state transition alone.
 */
export function shouldFlushOnStateChange(nextAiState: string): boolean {
  return nextAiState === 'idle';
}
