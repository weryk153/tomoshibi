import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { nextSpeechSubtitle } from './subtitle-hold.ts';

const base = {
  hasAudio: true,
  visibleText: '今天好嗎？',
  keepSubtitle: false,
  current: '你回來啦。',
  lastSpoken: '你回來啦。',
};

test('an ordinary spoken segment replaces the subtitle', () => {
  assert.equal(nextSpeechSubtitle(base), '今天好嗎？');
});

test('a laughter-only segment keeps the line she just said', () => {
  assert.equal(
    nextSpeechSubtitle({ ...base, visibleText: '哈↗哈↘哈↗！', keepSubtitle: true }),
    null,
  );
});

test('a laugh that opens the reply does not leave the thinking indicator up', () => {
  assert.equal(
    nextSpeechSubtitle({
      ...base, visibleText: '哈哈哈！', keepSubtitle: true, current: '思考中…',
    }),
    '哈哈哈！',
  );
});

test('a laugh after the subtitle was cleared is shown', () => {
  assert.equal(
    nextSpeechSubtitle({
      ...base, visibleText: 'ふふっ', keepSubtitle: true, current: '',
    }),
    'ふふっ',
  );
});

test('a laugh while a notice is on screen is shown', () => {
  assert.equal(
    nextSpeechSubtitle({
      ...base, visibleText: 'www', keepSubtitle: true, current: '新對話已開始',
    }),
    'www',
  );
});

test('a laugh before she has spoken at all is shown', () => {
  assert.equal(
    nextSpeechSubtitle({
      ...base, visibleText: 'haha', keepSubtitle: true, current: '', lastSpoken: null,
    }),
    'haha',
  );
});

test('a silent segment never touches the subtitle', () => {
  assert.equal(nextSpeechSubtitle({ ...base, hasAudio: false }), null);
  assert.equal(
    nextSpeechSubtitle({ ...base, hasAudio: false, keepSubtitle: true }),
    null,
  );
});
