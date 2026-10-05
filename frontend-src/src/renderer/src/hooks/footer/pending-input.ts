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

/** Send now, or hold it for when she's done talking? */
export function shouldQueueInsteadOfSending(aiState: string): boolean {
  return aiState === 'thinking-speaking';
}

/**
 * Whether reaching `nextAiState` is the signal to flush the queue.
 *
 * Deliberately narrow: only a genuine return to `idle` (normally
 * conversation-chain-end, but also e.g. config-switched/set-model-and-conf
 * after a character switch) counts. `interrupted` does NOT flush — the user
 * explicitly cut her off, which is a different action from "she finished",
 * and the queue should wait for the next real idle rather than firing
 * immediately off the back of an interrupt.
 */
export function shouldFlushOnStateChange(nextAiState: string): boolean {
  return nextAiState === 'idle';
}
