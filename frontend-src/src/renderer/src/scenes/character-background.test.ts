import test from 'node:test';
import assert from 'node:assert/strict';
import { createDefaultScene } from './scene.ts';
import { withThemeBackground, STARLIGHT_BACKGROUND, WITCH_BACKGROUND } from './character-background.ts';

test('the untouched default scene uses the moonlight room', () => {
  const saved = createDefaultScene('Background');
  assert.equal(withThemeBackground(saved).sourceUrl, WITCH_BACKGROUND);
  assert.notEqual(saved.sourceUrl, WITCH_BACKGROUND);
});

test('custom selections, uploaded assets, and performance scenes retain their backgrounds', () => {
  const defaultScene = createDefaultScene('Background');
  for (const scene of [
    { ...defaultScene, sourceUrl: STARLIGHT_BACKGROUND },
    { ...defaultScene, sourceUrl: '/bg/custom.png' },
    { ...defaultScene, assetKey: 'user-upload' },
    { ...defaultScene, id: 'performance-room' },
    { ...defaultScene, type: 'video' as const },
  ]) assert.equal(withThemeBackground(scene), scene);
});
