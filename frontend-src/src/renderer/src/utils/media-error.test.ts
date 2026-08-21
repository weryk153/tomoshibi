import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import {
  classifyMediaError,
  cameraErrorKey,
  isScreenPickerDismissed,
  microphoneErrorKey,
} from './media-error.ts';

const domError = (name: string): Error => Object.assign(new Error('x'), { name });

test('separates the three remedies a camera failure can need', () => {
  // These are not cosmetic variants: no permission, no device and device-busy
  // require completely different actions from the user.
  assert.equal(classifyMediaError(domError('NotAllowedError')), 'denied');
  assert.equal(classifyMediaError(domError('NotFoundError')), 'notFound');
  assert.equal(classifyMediaError(domError('NotReadableError')), 'inUse');
});

test('falls back to unknown rather than guessing', () => {
  assert.equal(classifyMediaError(domError('SomeFutureError')), 'unknown');
  assert.equal(classifyMediaError(null), 'unknown');
  assert.equal(classifyMediaError(undefined), 'unknown');
  assert.equal(classifyMediaError('a bare string'), 'unknown');
});

test('every kind maps to a real camera message key', () => {
  const keys = [
    domError('NotAllowedError'),
    domError('NotFoundError'),
    domError('NotReadableError'),
    domError('Whatever'),
  ].map(cameraErrorKey);

  assert.equal(new Set(keys).size, 4, 'each kind needs its own message');
  for (const key of keys) {
    assert.match(key, /^settings\.general\.camera/);
  }
});

test('a dismissed screen picker is not reported as a failure', () => {
  // getDisplayMedia rejects with NotAllowedError when the user simply closes
  // the "choose what to share" dialog. Treating that as an error tells people
  // they broke something when they only changed their mind.
  assert.equal(isScreenPickerDismissed(domError('NotAllowedError')), true);
});

test('a genuine screen-capture failure is still reported', () => {
  assert.equal(isScreenPickerDismissed(domError('NotReadableError')), false);
  assert.equal(isScreenPickerDismissed(domError('NotFoundError')), false);
  assert.equal(isScreenPickerDismissed(new Error('boom')), false);
});

test('microphone permission problems get an actionable message', () => {
  assert.equal(microphoneErrorKey(domError('NotAllowedError')), 'error.micDenied');
  assert.equal(microphoneErrorKey(domError('NotFoundError')), 'error.micNotFound');
  assert.equal(microphoneErrorKey(domError('NotReadableError')), 'error.micInUse');
});

test('a non-permission VAD failure keeps its diagnostic instead of a generic line', () => {
  // MicVAD can also fail because onnxruntime or wasm did not load. There is no
  // useful advice for that, and the raw error is the only clue the user can
  // pass on — returning null tells the caller to keep showing it.
  assert.equal(microphoneErrorKey(new Error('failed to load onnx model')), null);
  assert.equal(microphoneErrorKey(domError('SomeWasmError')), null);
});
