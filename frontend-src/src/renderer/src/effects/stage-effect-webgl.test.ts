import assert from 'node:assert/strict';
import test from 'node:test';
import {
  resolveStageEffectWebGLSize,
  stageEffectHexToRgb,
  STAGE_EFFECT_WEBGL_MAX_DIMENSION,
  STAGE_EFFECT_WEBGL_MAX_PIXELS,
} from './stage-effect-webgl.ts';

test('WebGL 特效層限制 DPR，避免 Electron 高解析度螢幕浪費 GPU', () => {
  assert.deepEqual(resolveStageEffectWebGLSize(800, 600, 3), {
    width: 1600,
    height: 1200,
    dpr: 2,
  });
});

test('超大視窗進一步降低 DPR，不建立超過 GPU 安全尺寸的 framebuffer', () => {
  const result = resolveStageEffectWebGLSize(3000, 2000, 2);
  assert.ok(Math.max(result.width, result.height) <= STAGE_EFFECT_WEBGL_MAX_DIMENSION);
  assert.ok(result.width * result.height <= STAGE_EFFECT_WEBGL_MAX_PIXELS);
  assert.ok(result.dpr < 2);
});

test('無效的視窗尺寸與 DPR 會安全回退', () => {
  assert.deepEqual(resolveStageEffectWebGLSize(Number.NaN, 0, Number.NaN), {
    width: 1,
    height: 1,
    dpr: 1,
  });
});

test('人物十六進位配色會轉成 shader 使用的正規化 RGB', () => {
  assert.deepEqual(stageEffectHexToRgb('#ff8000'), [1, 128 / 255, 0]);
  assert.deepEqual(stageEffectHexToRgb('invalid'), [1, 1, 1]);
});
