import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import {
  EMPTY_PENDING_INPUT,
  enqueuePendingInput,
  hasPendingInput,
  joinPendingInput,
  clearPendingInput,
  mergeQueuedWithImmediate,
  shouldQueueInsteadOfSending,
  shouldFlushOnStateChange,
} from './pending-input.ts';

test('empty queue has nothing pending', () => {
  assert.equal(hasPendingInput(EMPTY_PENDING_INPUT), false);
  assert.equal(joinPendingInput(EMPTY_PENDING_INPUT), '');
});

test('queues text typed while she is speaking', () => {
  const state = enqueuePendingInput(EMPTY_PENDING_INPUT, 'hello');
  assert.equal(hasPendingInput(state), true);
  assert.equal(joinPendingInput(state), 'hello');
});

test('blank or whitespace-only text is dropped, not queued', () => {
  const state = enqueuePendingInput(EMPTY_PENDING_INPUT, '   ');
  assert.equal(hasPendingInput(state), false);
});

test('multiple messages typed while speaking join in order with newlines', () => {
  let state = EMPTY_PENDING_INPUT;
  state = enqueuePendingInput(state, 'first');
  state = enqueuePendingInput(state, 'second');
  state = enqueuePendingInput(state, 'third');
  assert.equal(joinPendingInput(state), 'first\nsecond\nthird');
});

test('does not mutate the previous state (pure)', () => {
  const before = enqueuePendingInput(EMPTY_PENDING_INPUT, 'a');
  const after = enqueuePendingInput(before, 'b');
  assert.equal(joinPendingInput(before), 'a');
  assert.equal(joinPendingInput(after), 'a\nb');
});

test('clearPendingInput empties the queue', () => {
  const state = enqueuePendingInput(EMPTY_PENDING_INPUT, 'hello');
  assert.equal(hasPendingInput(clearPendingInput()), false);
  // clearing never looks at `state` — it just yields the empty queue
  void state;
});

test('thinking-speaking queues instead of sending immediately', () => {
  assert.equal(shouldQueueInsteadOfSending('thinking-speaking'), true);
});

test('idle (and every other state) sends immediately, no queueing', () => {
  assert.equal(shouldQueueInsteadOfSending('idle'), false);
  assert.equal(shouldQueueInsteadOfSending('listening'), false);
  assert.equal(shouldQueueInsteadOfSending('waiting'), false);
  assert.equal(shouldQueueInsteadOfSending('interrupted'), false);
  assert.equal(shouldQueueInsteadOfSending('loading'), false);
});

test('flushes on reaching idle', () => {
  assert.equal(shouldFlushOnStateChange('idle'), true);
});

test('does not flush while still speaking', () => {
  assert.equal(shouldFlushOnStateChange('thinking-speaking'), false);
});

test('does not flush on interrupted — that is a different action from "she finished"', () => {
  assert.equal(shouldFlushOnStateChange('interrupted'), false);
});

test('does not flush on transient states like listening/waiting/loading', () => {
  assert.equal(shouldFlushOnStateChange('listening'), false);
  assert.equal(shouldFlushOnStateChange('waiting'), false);
  assert.equal(shouldFlushOnStateChange('loading'), false);
});

test('immediate send with nothing queued goes out unchanged', () => {
  assert.equal(mergeQueuedWithImmediate(EMPTY_PENDING_INPUT, 'hello'), 'hello');
});

test('immediate send after interrupt prepends anything still queued, in order', () => {
  // Typed while she was speaking (queued), then the user hit interrupt and
  // immediately sent another message before the queue had a chance to
  // auto-flush: the older queued text must go out ahead of the new one, not
  // after — chat history already shows it first.
  let state = EMPTY_PENDING_INPUT;
  state = enqueuePendingInput(state, 'typed while she was speaking');
  assert.equal(
    mergeQueuedWithImmediate(state, 'sent right after interrupt'),
    'typed while she was speaking\nsent right after interrupt',
  );
});

test('merging an immediate send does not mutate the queued state', () => {
  const state = enqueuePendingInput(EMPTY_PENDING_INPUT, 'queued');
  mergeQueuedWithImmediate(state, 'new');
  assert.equal(joinPendingInput(state), 'queued');
});
