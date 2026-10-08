import assert from 'node:assert/strict';
import test from 'node:test';
import { lastLine } from './extras.ts';

test('安裝進度只顯示 uv 最新那一行，空行與其他事件不改', () => {
  assert.equal(lastLine({ status: 'installing', line: 'Prepared 12 packages' }, '舊的'), 'Prepared 12 packages');
  assert.equal(lastLine({ status: 'installing', line: '' }, '舊的'), '舊的');
  assert.equal(lastLine({ status: 'success' }, '舊的'), '舊的');
});
