import assert from 'node:assert/strict';
import test from 'node:test';
import {
  registerStageEffectBinding,
  resolveStageEffectBinding,
  resolveStageEffectCharacterId,
  STAGE_INTERACTION_CUE_EVENT,
  STAGE_MOTION_CUE_EVENT,
} from './stage-effect-bindings.ts';

test('Kurisu 只在人物登場演出綁定 Signature 動作', () => {
  const binding = resolveStageEffectBinding('kurisu_fan', 'characterEntrance');
  assert.equal(binding.title, 'LAB MEM 004');
  assert.deepEqual(binding.motionCues, [{
    atMs: 1450,
    actionId: 'signature',
    group: 'Signature',
    index: 0,
    priority: 3,
  }]);
});

test('Kurisu 不會錯綁通用必殺技特效', () => {
  const binding = resolveStageEffectBinding('kurisu_fan', 'cinematicBurst');
  assert.deepEqual(binding.motionCues, []);
  assert.equal(binding.title, undefined);
});

test('未知人物會回退成沒有硬綁身體動作的通用演出', () => {
  const binding = resolveStageEffectBinding('new_character', 'cinematicBurst');
  assert.deepEqual(binding.motionCues, []);
  assert.equal(binding.interactionCues[0].action, 'cinematic-focus');
});

test('真正有專屬招式的人物可以登記自己的動作與畫面配色', () => {
  registerStageEffectBinding('test_hero', 'cinematicBurst', {
    title: 'TEST DRIVE',
    palette: {
      primary: '#123456',
      accent: '#abcdef',
      glow: '#fedcba',
      void: '#000000',
    },
    motionCues: [{
      atMs: 900,
      actionId: 'signature',
      group: 'Special',
      index: 2,
      priority: 3,
    }],
    interactionCues: [],
  });

  const binding = resolveStageEffectBinding('test_hero', 'cinematicBurst');
  assert.equal(binding.title, 'TEST DRIVE');
  assert.equal(binding.motionCues[0].actionId, 'signature');
  assert.equal(binding.motionCues[0].group, 'Special');
});

test('每次解析都回傳副本，執行期修改不會污染註冊資料', () => {
  const first = resolveStageEffectBinding('test_hero', 'cinematicBurst');
  first.motionCues[0].group = 'Broken';
  const second = resolveStageEffectBinding('test_hero', 'cinematicBurst');
  assert.equal(second.motionCues[0].group, 'Special');
});

test('3a 與 3b 的整合事件名稱固定', () => {
  assert.equal(STAGE_MOTION_CUE_EVENT, 'tomoshibi:stage-motion-cue');
  assert.equal(STAGE_INTERACTION_CUE_EVENT, 'tomoshibi:stage-interaction-cue');
});

test('人物 ID 優先使用名稱，舊模型資料可從 URL 回退', () => {
  assert.equal(resolveStageEffectCharacterId({
    name: 'kurisu_fan',
    url: '/live2d-models/other/model.model3.json',
  }), 'kurisu_fan');
  assert.equal(resolveStageEffectCharacterId({
    url: 'http://127.0.0.1:12393/live2d-models/kurisu_fan/kurisu.model3.json',
  }), 'kurisu_fan');
});
