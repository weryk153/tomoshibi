import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { chipLabel, MOOD_WORDS } from './character-chip.ts';
import { MOOD_FLOOR } from '../../avatar/mood.ts';

// 假的 t：把 key 原樣吐回來，測試只看選了哪個 key。
const t = (key: string): string => key;

test('idle shows her mood', () => {
  assert.deepEqual(
    chipLabel({ aiState: 'idle', mood: 'happy', intensity: 0.8, t }),
    { text: 'mood.happy', tone: 'accent' },
  );
});

test('every mood word maps to its own i18n key', () => {
  for (const word of MOOD_WORDS) {
    const label = chipLabel({ aiState: 'idle', mood: word, intensity: 1, t });
    assert.equal(label.text, word === 'neutral' ? 'mood.neutral' : `mood.${word}`);
  }
});

test('dot colour follows the mood family', () => {
  const tone = (mood: string) => chipLabel({ aiState: 'idle', mood, intensity: 1, t }).tone;
  assert.equal(tone('neutral'), 'muted');
  assert.equal(tone('calm'), 'muted');
  assert.equal(tone('happy'), 'accent');
  assert.equal(tone('surprised'), 'accent');
  assert.equal(tone('angry'), 'danger');
  assert.equal(tone('sad'), 'accent2');
  assert.equal(tone('worried'), 'accent2');
  assert.equal(tone('embarrassed'), 'accentSoft');
});

test('a mood faded below the floor reads as neutral', () => {
  assert.deepEqual(
    chipLabel({ aiState: 'idle', mood: 'angry', intensity: MOOD_FLOOR - 0.01, t }),
    { text: 'mood.neutral', tone: 'muted' },
  );
});

test('a mood exactly at the floor still shows', () => {
  assert.equal(
    chipLabel({ aiState: 'idle', mood: 'angry', intensity: MOOD_FLOOR, t }).text,
    'mood.angry',
  );
});

test('a mood word the engine invents later falls back to neutral', () => {
  assert.deepEqual(
    chipLabel({ aiState: 'idle', mood: 'nostalgic', intensity: 0.9, t }),
    { text: 'mood.neutral', tone: 'muted' },
  );
});

test('a non-idle state replaces the mood with the state label', () => {
  for (const aiState of ['thinking-speaking', 'listening', 'interrupted', 'loading']) {
    assert.deepEqual(
      chipLabel({ aiState, mood: 'happy', intensity: 0.9, t }),
      { text: `aiState.${aiState}`, tone: 'busy' },
    );
  }
});

test('back to idle returns to the mood', () => {
  const busy = chipLabel({ aiState: 'thinking-speaking', mood: 'sad', intensity: 0.5, t });
  const idle = chipLabel({ aiState: 'idle', mood: 'sad', intensity: 0.5, t });
  assert.equal(busy.tone, 'busy');
  assert.deepEqual(idle, { text: 'mood.sad', tone: 'accent2' });
});

test('waiting (the user is typing) keeps showing the mood instead of flickering', () => {
  // use-footer 每按一個鍵就把狀態設成 waiting，2 秒後回 idle；
  // 膠囊要是跟著換字，打字時會在「心情」和「等待中」之間一直閃。
  assert.deepEqual(
    chipLabel({ aiState: 'waiting', mood: 'happy', intensity: 0.8, t }),
    { text: 'mood.happy', tone: 'accent' },
  );
});
