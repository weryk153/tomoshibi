import assert from 'node:assert/strict';
import test from 'node:test';
import {
  STAGE_EFFECT_MUSIC_MAX_BYTES,
  stageEffectMusicKey,
  validateStageEffectMusic,
} from './stage-effect-music.ts';

test('人物與演出組成互不衝突的音樂槽 key', () => {
  assert.equal(
    stageEffectMusicKey('kurisu_fan', 'characterEntrance'),
    'kurisu_fan::characterEntrance',
  );
});

test('接受常用的本機音樂格式，MIME 缺失時可依副檔名回退', () => {
  assert.equal(validateStageEffectMusic({
    name: 'entry.mp3',
    size: 1024,
    type: 'audio/mpeg',
  }), null);
  assert.equal(validateStageEffectMusic({
    name: 'entry.M4A',
    size: 1024,
    type: '',
  }), null);
});

test('拒絕非音樂、空檔與超過 30MB 的音檔', () => {
  assert.equal(validateStageEffectMusic({
    name: 'image.png',
    size: 1024,
    type: 'image/png',
  }), 'notAudio');
  assert.equal(validateStageEffectMusic({
    name: 'empty.mp3',
    size: 0,
    type: 'audio/mpeg',
  }), 'empty');
  assert.equal(validateStageEffectMusic({
    name: 'huge.mp3',
    size: STAGE_EFFECT_MUSIC_MAX_BYTES + 1,
    type: 'audio/mpeg',
  }), 'tooLarge');
});
