import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildStageDirectorCandidates,
  createDefaultStagePerformancePool,
  createStagePerformanceRuntimeState,
  normalizeStagePerformanceStore,
  recordStagePerformancePlayed,
  selectStagePerformance,
  type StagePerformancePool,
  type StagePerformancePreset,
} from './stage-performance.ts';

function preset(id: string, overrides: Partial<StagePerformancePreset> = {}): StagePerformancePreset {
  return {
    id,
    builtin: false,
    name: id,
    description: id,
    effectId: 'characterEntrance',
    scale: 'scene',
    intensity: 1,
    sound: true,
    triggers: ['conversation'],
    weight: 1,
    cooldownMs: 0,
    probability: 1,
    conditions: { keywords: [], timePeriods: [] },
    musicVolume: 0.5,
    musicFadeInMs: 300,
    musicFadeOutMs: 500,
    ...overrides,
  };
}

function pool(overrides: Partial<StagePerformancePool> = {}): StagePerformancePool {
  return {
    enabled: true,
    mode: 'shuffle',
    selectedIds: ['one', 'two', 'three'],
    avoidRecent: 1,
    ...overrides,
  };
}

test('預設人物登場池選好角色專屬方案但不擅自啟用', () => {
  assert.deepEqual(createDefaultStagePerformancePool('kurisu_fan', 'entrance'), {
    enabled: false,
    mode: 'shuffle',
    selectedIds: ['kurisu-lab-mem-004'],
    avoidRecent: 1,
  });
});

test('洗牌袋在所有已選方案播完前不重複', () => {
  const presets = [preset('one'), preset('two'), preset('three')];
  const state = createStagePerformanceRuntimeState();
  const context = { trigger: 'conversation' as const, characterId: 'test' };
  const selected = Array.from({ length: 3 }, () => {
    const result = selectStagePerformance(presets, pool(), context, state, {
      random: () => 0.4,
    });
    assert.ok(result);
    recordStagePerformancePlayed(state, result.id, 'conversation');
    return result.id;
  });
  assert.equal(new Set(selected).size, 3);
});

test('冷卻與最近播放排除後，仍可從其他方案選擇', () => {
  const presets = [
    preset('one', { cooldownMs: 60_000 }),
    preset('two'),
  ];
  const state = createStagePerformanceRuntimeState();
  recordStagePerformancePlayed(state, 'one', 'conversation', 10_000);
  const selected = selectStagePerformance(
    presets,
    pool({ selectedIds: ['one', 'two'] }),
    {
      trigger: 'conversation',
      characterId: 'test',
      now: new Date(20_000),
    },
    state,
    { random: () => 0 },
  );
  assert.equal(selected?.id, 'two');
});

test('條件方案會檢查關鍵字與時段', () => {
  const conditioned = preset('one', {
    conditions: { keywords: ['world line'], timePeriods: ['night'] },
  });
  const state = createStagePerformanceRuntimeState();
  assert.equal(selectStagePerformance(
    [conditioned],
    pool({ mode: 'conditions', selectedIds: ['one'] }),
    {
      trigger: 'conversation',
      text: 'That world line changed.',
      now: new Date('2026-07-31T23:00:00'),
    },
    state,
    { random: () => 0 },
  )?.id, 'one');
  assert.equal(selectStagePerformance(
    [conditioned],
    pool({ mode: 'conditions', selectedIds: ['one'] }),
    {
      trigger: 'conversation',
      text: 'Normal topic',
      now: new Date('2026-07-31T23:00:00'),
    },
    state,
    { random: () => 0 },
  ), null);
});

test('AI 模式只接受候選池內且條件相容的方案', () => {
  const presets = [preset('one'), preset('two')];
  const state = createStagePerformanceRuntimeState();
  const aiPool = pool({ mode: 'ai', selectedIds: ['one'] });
  assert.equal(selectStagePerformance(
    presets,
    aiPool,
    { trigger: 'conversation', characterId: 'test' },
    state,
    { requestedPresetId: 'one' },
  )?.id, 'one');
  assert.equal(selectStagePerformance(
    presets,
    aiPool,
    { trigger: 'conversation', characterId: 'test' },
    state,
    { requestedPresetId: 'two' },
  ), null);
  assert.equal(selectStagePerformance(
    [preset('one', { probability: 0 })],
    aiPool,
    { trigger: 'conversation', characterId: 'test' },
    createStagePerformanceRuntimeState(),
    { requestedPresetId: 'one', random: () => 0.5 },
  ), null);
});

test('只把已複選且相容的方案提供給 AI 導演', () => {
  const candidates = buildStageDirectorCandidates(
    [
      preset('one'),
      preset('two', { characterIds: ['other'] }),
      preset('three'),
    ],
    pool({ mode: 'hybrid', selectedIds: ['one', 'two'] }),
    'test',
    'conversation',
  );
  assert.deepEqual(candidates.map((candidate) => candidate.id), ['one']);
});

test('儲存資料會移除重複、冒用內建 ID 與失效的播放池項目', () => {
  const normalized = normalizeStagePerformanceStore({
    version: 1,
    customPresets: [
      preset('custom'),
      preset('custom'),
      preset('character-entrance'),
    ],
    poolsByCharacter: {
      test: {
        conversation: pool({
          selectedIds: ['custom', 'character-entrance', 'missing'],
        }),
      },
    },
  });
  assert.deepEqual(normalized.customPresets.map((item) => item.id), ['custom']);
  assert.deepEqual(
    normalized.poolsByCharacter.test?.conversation?.selectedIds,
    ['custom', 'character-entrance'],
  );
});
