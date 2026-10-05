import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { nextSpeechSubtitle, replaceSubtitleText } from './subtitle-hold.ts';

const base = {
  hasAudio: true,
  visibleText: '今天好嗎？',
  keepSubtitle: false,
  current: '你回來啦。',
  lastSpoken: '你回來啦。',
};

test('an ordinary spoken segment replaces the subtitle', () => {
  assert.deepEqual(nextSpeechSubtitle(base), { text: '今天好嗎？', spoken: null });
});

test('a laughter-only segment keeps the line she just said', () => {
  assert.equal(
    nextSpeechSubtitle({ ...base, visibleText: '哈↗哈↘哈↗！', keepSubtitle: true }),
    null,
  );
});

test('a laugh that opens the reply does not leave the thinking indicator up', () => {
  assert.deepEqual(
    nextSpeechSubtitle({
      ...base, visibleText: '哈哈哈！', keepSubtitle: true, current: '思考中…',
    }),
    { text: '哈哈哈！', spoken: null },
  );
});

test('a laugh after the subtitle was cleared is shown', () => {
  assert.deepEqual(
    nextSpeechSubtitle({
      ...base, visibleText: 'ふふっ', keepSubtitle: true, current: '',
    }),
    { text: 'ふふっ', spoken: null },
  );
});

test('a laugh while a notice is on screen is shown', () => {
  assert.deepEqual(
    nextSpeechSubtitle({
      ...base, visibleText: 'www', keepSubtitle: true, current: '新對話已開始',
    }),
    { text: 'www', spoken: null },
  );
});

test('a laugh before she has spoken at all is shown', () => {
  assert.deepEqual(
    nextSpeechSubtitle({
      ...base, visibleText: 'haha', keepSubtitle: true, current: '', lastSpoken: null,
    }),
    { text: 'haha', spoken: null },
  );
});

test('a silent segment never touches the subtitle', () => {
  assert.equal(nextSpeechSubtitle({ ...base, hasAudio: false }), null);
  assert.equal(
    nextSpeechSubtitle({ ...base, hasAudio: false, keepSubtitle: true }),
    null,
  );
});

// 雙語字幕：後端在 payload 帶 spoken_text（她實際唸的那句）時，畫面上兩行。

test('a segment with a spoken line shows both lines', () => {
  assert.deepEqual(
    nextSpeechSubtitle({ ...base, spokenText: '今日は元気？' }),
    { text: '今天好嗎？', spoken: '今日は元気？' },
  );
});

test('a spoken line that reads the same as the subtitle shows once', () => {
  assert.deepEqual(
    nextSpeechSubtitle({ ...base, spokenText: ' 今天好嗎？ ' }),
    { text: '今天好嗎？', spoken: null },
  );
  assert.deepEqual(
    nextSpeechSubtitle({ ...base, spokenText: '' }),
    { text: '今天好嗎？', spoken: null },
  );
});

test('a laughter-only segment keeps both lines of the previous one', () => {
  assert.equal(
    nextSpeechSubtitle({
      ...base, visibleText: '哈哈哈！', spokenText: 'ははは！', keepSubtitle: true,
    }),
    null,
  );
});

test('a silent segment with a spoken line still leaves the subtitle alone', () => {
  assert.equal(
    nextSpeechSubtitle({ ...base, hasAudio: false, spokenText: '今日は元気？' }),
    null,
  );
});

test('when something else replaces the text, the spoken line goes with it', () => {
  const twoLines = { text: '今天好嗎？', spoken: '今日は元気？' };
  assert.deepEqual(replaceSubtitleText(twoLines, ''), { text: '', spoken: null });
  assert.deepEqual(
    replaceSubtitleText(twoLines, '新對話已開始'),
    { text: '新對話已開始', spoken: null },
  );
  // 文字沒變（例如清除規則決定留著）就原封不動，上行也留著。
  assert.equal(replaceSubtitleText(twoLines, '今天好嗎？'), twoLines);
});
