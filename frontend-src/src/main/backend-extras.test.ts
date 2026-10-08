import assert from 'node:assert/strict';
import test from 'node:test';
import { syncArgs, readExtras } from './backend-extras.ts';

test('啟動同步：沒有裝過選裝套件時跟以前一模一樣', () => {
  assert.deepEqual(syncArgs([]), ['sync', '--frozen', '--no-dev', '--no-progress']);
});

test('啟動同步：裝過的選裝套件每個都帶上，不認得的不帶', () => {
  assert.deepEqual(
    syncArgs(['faster_whisper', 'rm -rf', 'faster_whisper']),
    ['sync', '--frozen', '--no-dev', '--no-progress', '--extra', 'faster_whisper'],
  );
});

test('extras.json 壞掉或不存在就當沒有', () => {
  assert.deepEqual(readExtras(() => '["faster_whisper"]'), ['faster_whisper']);
  assert.deepEqual(readExtras(() => '{not json'), []);
  assert.deepEqual(readExtras(() => '{"a": 1}'), []);
  assert.deepEqual(readExtras(() => { throw new Error('ENOENT'); }), []);
});
