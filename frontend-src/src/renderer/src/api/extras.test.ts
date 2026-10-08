import assert from 'node:assert/strict';
import test from 'node:test';
import { lastLine } from './extras.ts';

test('安裝進度只顯示 uv 最新那一行，空行與其他事件不改', () => {
  assert.equal(lastLine({ status: 'installing', line: 'Prepared 12 packages' }, '舊的'), 'Prepared 12 packages');
  assert.equal(lastLine({ status: 'installing', line: '' }, '舊的'), '舊的');
  assert.equal(lastLine({ status: 'success' }, '舊的'), '舊的');
});

test('語音模型下載進度：百分比與 MB；不知道總大小時只給已下載多少', async () => {
  const { modelProgress } = await import('./extras.ts');
  assert.deepEqual(modelProgress({ status: 'model', completed: 809e6, total: 1618e6 }), { percent: 50, doneMb: 809, totalMb: 1618 });
  assert.deepEqual(modelProgress({ status: 'model', completed: 300e6, total: 0 }), { percent: null, doneMb: 300, totalMb: null });
  assert.equal(modelProgress({ status: 'installing', line: 'x' }), null);
});
