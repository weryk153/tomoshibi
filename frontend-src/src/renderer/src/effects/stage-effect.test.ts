import assert from 'node:assert/strict';
import test from 'node:test';
import {
  createStageEffectRequest,
  getStageEffectDuration,
  isStageEffectId,
  isStageEffectScale,
  normalizeStageEffectOptions,
} from './stage-effect.ts';

test('只接受已註冊的演出 preset', () => {
  assert.equal(isStageEffectId('characterEntrance'), true);
  assert.equal(isStageEffectId('cinematicBurst'), true);
  assert.equal(isStageEffectId('ultimate'), false);
  assert.equal(isStageEffectId(null), false);
});

test('強度被限制在安全範圍，避免完全看不到或閃光過強', () => {
  assert.equal(normalizeStageEffectOptions({ intensity: -9 }).intensity, 0.35);
  assert.equal(normalizeStageEffectOptions({ intensity: 9 }).intensity, 1.5);
  assert.equal(normalizeStageEffectOptions({ intensity: Number.NaN }).intensity, 1);
});

test('標題會去除空白，空字串交回翻譯預設值', () => {
  const options = normalizeStageEffectOptions({
    title: '  CINEMATIC BURST  ',
    subtitle: '   ',
  });
  assert.equal(options.title, 'CINEMATIC BURST');
  assert.equal(options.subtitle, undefined);
});

test('演出請求具有完整預設值與固定時間軸長度', () => {
  assert.deepEqual(createStageEffectRequest('cinematicBurst'), {
    id: 'cinematicBurst',
    options: {
      title: undefined,
      subtitle: undefined,
      sound: true,
      intensity: 1,
      characterId: undefined,
      scale: 'cinematic',
      musicSlot: undefined,
      musicVolume: 0.5,
      musicFadeInMs: 350,
      musicFadeOutMs: 600,
    },
  });
  assert.equal(getStageEffectDuration('cinematicBurst'), 6200);
  assert.equal(getStageEffectDuration('characterEntrance'), 4800);
});

test('不同演出有合理的預設規模，也可以由呼叫端縮小', () => {
  assert.equal(
    createStageEffectRequest('characterEntrance').options.scale,
    'scene',
  );
  assert.equal(
    createStageEffectRequest('cinematicBurst', { scale: 'accent' }).options.scale,
    'accent',
  );
  assert.equal(isStageEffectScale('scene'), true);
  assert.equal(isStageEffectScale('huge'), false);
  assert.equal(
    createStageEffectRequest('characterEntrance', {
      scale: 'huge' as never,
    }).options.scale,
    'scene',
  );
});
