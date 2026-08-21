import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { resolveAutoClear, resolveConversationEndClear } from './subtitle-autoclear.ts';

test('clears the subtitle it was scheduled for', () => {
  assert.equal(resolveAutoClear('新對話已開始', '新對話已開始'), '');
});

test('leaves a subtitle that changed since the timer was set', () => {
  // The failure this guards: a notice schedules its removal, the character
  // starts speaking before it fires, and an unconditional clear blanks her
  // line while the audio is still playing.
  assert.equal(
    resolveAutoClear('今天天氣很好，我們出去走走吧。', '新對話已開始'),
    '今天天氣很好，我們出去走走吧。',
  );
});

test('does not resurrect text when the subtitle is already empty', () => {
  assert.equal(resolveAutoClear('', '沒聽清楚，再說一次？'), '');
});

test('treats an identical repeat as its own subtitle', () => {
  // Two misfires in a row produce the same string. The second set cancels the
  // first timer, so the surviving timer belongs to the text on screen and must
  // still be allowed to clear it.
  assert.equal(
    resolveAutoClear('沒聽清楚，再說一次？', '沒聽清楚，再說一次？'),
    '',
  );
});

test('轉場字幕在整輪結束時要清掉', () => {
  // 最後一句講完之後，畫面上留著的就是它——該清。
  assert.equal(resolveConversationEndClear('她最後說的那句話。'), '');
});

test('整輪結束時若已換成別的通知，不要動它', () => {
  // conversation-chain-end 排在音訊佇列尾端，中間可能已經插入了系統通知
  // （切換角色、新對話）。那是別人貼的，清掉會讓使用者少看到一則訊息。
  assert.equal(
    resolveConversationEndClear('新對話已開始', new Set(['新對話已開始'])),
    '新對話已開始',
  );
});

test('空字幕維持空的', () => {
  assert.equal(resolveConversationEndClear(''), '');
});
