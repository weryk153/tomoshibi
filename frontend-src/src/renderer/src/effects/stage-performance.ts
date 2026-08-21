import {
  isStageEffectId,
  isStageEffectScale,
  type StageEffectId,
  type StageEffectScale,
} from './stage-effect.ts';

export const STAGE_PERFORMANCE_TRIGGERS = [
  'entrance',
  'conversation',
  'proactive',
  'manual',
] as const;

export const STAGE_PERFORMANCE_MODES = [
  'fixed',
  'shuffle',
  'sequence',
  'weighted',
  'conditions',
  'ai',
  'hybrid',
] as const;

export const STAGE_TIME_PERIODS = [
  'morning',
  'day',
  'evening',
  'night',
] as const;

export type StagePerformanceTrigger = (typeof STAGE_PERFORMANCE_TRIGGERS)[number];
export type StagePerformanceMode = (typeof STAGE_PERFORMANCE_MODES)[number];
export type StageTimePeriod = (typeof STAGE_TIME_PERIODS)[number];

export interface StagePerformanceConditions {
  keywords: string[];
  timePeriods: StageTimePeriod[];
}

export interface StagePerformancePreset {
  id: string;
  builtin: boolean;
  name: string;
  description: string;
  effectId: StageEffectId;
  scale: StageEffectScale;
  intensity: number;
  sound: boolean;
  title?: string;
  subtitle?: string;
  characterIds?: string[];
  triggers: StagePerformanceTrigger[];
  weight: number;
  cooldownMs: number;
  probability: number;
  conditions: StagePerformanceConditions;
  musicVolume: number;
  musicFadeInMs: number;
  musicFadeOutMs: number;
}

export interface StagePerformancePool {
  enabled: boolean;
  mode: StagePerformanceMode;
  selectedIds: string[];
  avoidRecent: number;
}

export interface StagePerformanceStore {
  version: 1;
  customPresets: StagePerformancePreset[];
  poolsByCharacter: Record<
    string,
    Partial<Record<StagePerformanceTrigger, StagePerformancePool>>
  >;
}

export interface StagePerformanceSelectionContext {
  characterId?: string;
  trigger: StagePerformanceTrigger;
  text?: string;
  now?: Date;
}

export interface StagePerformanceHistoryEntry {
  presetId: string;
  trigger: StagePerformanceTrigger;
  playedAt: number;
}

export interface StagePerformanceRuntimeState {
  history: StagePerformanceHistoryEntry[];
  sequenceByPool: Record<string, number>;
  shuffleBags: Record<string, string[]>;
}

export interface StageDirectorCandidate {
  id: string;
  name: string;
  description: string;
  triggers: StagePerformanceTrigger[];
}

export const BUILTIN_STAGE_PERFORMANCES: readonly StagePerformancePreset[] = [
  {
    id: 'subtle-accent',
    builtin: true,
    name: 'Subtle Accent',
    description: 'A short, quiet visual accent for ordinary reactions.',
    effectId: 'characterEntrance',
    scale: 'accent',
    intensity: 0.65,
    sound: false,
    triggers: ['conversation', 'proactive', 'manual'],
    weight: 1,
    cooldownMs: 90_000,
    probability: 0.35,
    conditions: { keywords: [], timePeriods: [] },
    musicVolume: 0.45,
    musicFadeInMs: 250,
    musicFadeOutMs: 400,
  },
  {
    id: 'character-entrance',
    builtin: true,
    name: 'Character Entrance',
    description: 'A general identity card, scan and camera entrance.',
    effectId: 'characterEntrance',
    scale: 'scene',
    intensity: 1,
    sound: true,
    triggers: ['entrance', 'manual'],
    weight: 1,
    cooldownMs: 15_000,
    probability: 1,
    conditions: { keywords: [], timePeriods: [] },
    musicVolume: 0.5,
    musicFadeInMs: 450,
    musicFadeOutMs: 650,
  },
  {
    id: 'kurisu-lab-mem-004',
    builtin: true,
    name: 'LAB MEM 004',
    description: 'Kurisu laboratory identity scan and signature entrance.',
    effectId: 'characterEntrance',
    scale: 'scene',
    intensity: 1,
    sound: true,
    title: 'LAB MEM 004',
    subtitle: 'MAKISE KURISU',
    characterIds: ['kurisu_fan'],
    triggers: ['entrance', 'manual'],
    weight: 1,
    cooldownMs: 15_000,
    probability: 1,
    conditions: { keywords: [], timePeriods: [] },
    musicVolume: 0.5,
    musicFadeInMs: 450,
    musicFadeOutMs: 650,
  },
  {
    id: 'cinematic-burst',
    builtin: true,
    name: 'Cinematic Burst',
    description: 'A large full-screen impact performance for suitable characters.',
    effectId: 'cinematicBurst',
    scale: 'cinematic',
    intensity: 1,
    sound: true,
    triggers: ['conversation', 'manual'],
    weight: 1,
    cooldownMs: 300_000,
    probability: 0.2,
    conditions: { keywords: [], timePeriods: [] },
    musicVolume: 0.58,
    musicFadeInMs: 250,
    musicFadeOutMs: 800,
  },
] as const;

export function createEmptyStagePerformanceStore(): StagePerformanceStore {
  return {
    version: 1,
    customPresets: [],
    poolsByCharacter: {},
  };
}

function isTrigger(value: unknown): value is StagePerformanceTrigger {
  return typeof value === 'string'
    && STAGE_PERFORMANCE_TRIGGERS.includes(value as StagePerformanceTrigger);
}

function isMode(value: unknown): value is StagePerformanceMode {
  return typeof value === 'string'
    && STAGE_PERFORMANCE_MODES.includes(value as StagePerformanceMode);
}

function normalizeFiniteNumber(
  value: unknown,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  const number = Number(value);
  return Number.isFinite(number)
    ? Math.min(maximum, Math.max(minimum, number))
    : fallback;
}

function normalizeCustomPreset(value: unknown): StagePerformancePreset | null {
  if (!value || typeof value !== 'object') return null;
  const item = value as Partial<StagePerformancePreset>;
  const id = String(item.id || '').trim();
  const name = String(item.name || '').trim();
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/i.test(id) || !name) return null;
  if (!isStageEffectId(item.effectId) || !isStageEffectScale(item.scale)) return null;

  const triggers = Array.isArray(item.triggers)
    ? item.triggers.filter(isTrigger)
    : [];
  return {
    id,
    builtin: false,
    name: name.slice(0, 80),
    description: String(item.description || '').trim().slice(0, 240),
    effectId: item.effectId,
    scale: item.scale,
    intensity: normalizeFiniteNumber(item.intensity, 1, 0.35, 1.5),
    sound: item.sound !== false,
    title: String(item.title || '').trim().slice(0, 80) || undefined,
    subtitle: String(item.subtitle || '').trim().slice(0, 80) || undefined,
    characterIds: Array.isArray(item.characterIds)
      ? item.characterIds.map(String).map((entry) => entry.trim()).filter(Boolean).slice(0, 20)
      : undefined,
    triggers: triggers.length > 0 ? triggers : ['manual'],
    weight: normalizeFiniteNumber(item.weight, 1, 0.01, 100),
    cooldownMs: normalizeFiniteNumber(item.cooldownMs, 0, 0, 86_400_000),
    probability: normalizeFiniteNumber(item.probability, 1, 0, 1),
    conditions: {
      keywords: Array.isArray(item.conditions?.keywords)
        ? item.conditions.keywords.map(String).map((entry) => entry.trim())
          .filter(Boolean).slice(0, 30)
        : [],
      timePeriods: Array.isArray(item.conditions?.timePeriods)
        ? item.conditions.timePeriods.filter((period): period is StageTimePeriod => (
          STAGE_TIME_PERIODS.includes(period as StageTimePeriod)
        ))
        : [],
    },
    musicVolume: normalizeFiniteNumber(item.musicVolume, 0.5, 0, 1),
    musicFadeInMs: normalizeFiniteNumber(item.musicFadeInMs, 350, 0, 10_000),
    musicFadeOutMs: normalizeFiniteNumber(item.musicFadeOutMs, 600, 0, 10_000),
  };
}

function normalizePool(value: unknown): StagePerformancePool | null {
  if (!value || typeof value !== 'object') return null;
  const item = value as Partial<StagePerformancePool>;
  return {
    enabled: item.enabled === true,
    mode: isMode(item.mode) ? item.mode : 'shuffle',
    selectedIds: Array.isArray(item.selectedIds)
      ? [...new Set(item.selectedIds.map(String).map((id) => id.trim()).filter(Boolean))]
        .slice(0, 50)
      : [],
    avoidRecent: Math.round(normalizeFiniteNumber(item.avoidRecent, 1, 0, 10)),
  };
}

export function normalizeStagePerformanceStore(
  value: unknown,
): StagePerformanceStore {
  if (!value || typeof value !== 'object') return createEmptyStagePerformanceStore();
  const raw = value as Partial<StagePerformanceStore>;
  const normalizedCustomPresets = Array.isArray(raw.customPresets)
    ? raw.customPresets
      .map(normalizeCustomPreset)
      .filter((preset): preset is StagePerformancePreset => Boolean(preset))
    : [];
  const reservedIds = new Set(BUILTIN_STAGE_PERFORMANCES.map((preset) => preset.id));
  const customPresets = normalizedCustomPresets.filter((preset) => {
    if (reservedIds.has(preset.id)) return false;
    reservedIds.add(preset.id);
    return true;
  });
  const validPresetIds = reservedIds;
  const poolsByCharacter: StagePerformanceStore['poolsByCharacter'] = {};
  if (raw.poolsByCharacter && typeof raw.poolsByCharacter === 'object') {
    Object.entries(raw.poolsByCharacter).slice(0, 100).forEach(([characterId, pools]) => {
      if (!pools || typeof pools !== 'object') return;
      const normalizedPools: Partial<
        Record<StagePerformanceTrigger, StagePerformancePool>
      > = {};
      Object.entries(pools).forEach(([trigger, pool]) => {
        if (!isTrigger(trigger)) return;
        const normalized = normalizePool(pool);
        if (normalized) {
          normalizedPools[trigger] = {
            ...normalized,
            selectedIds: normalized.selectedIds.filter((id) => validPresetIds.has(id)),
          };
        }
      });
      poolsByCharacter[characterId] = normalizedPools;
    });
  }
  return { version: 1, customPresets, poolsByCharacter };
}

export function createStagePerformanceRuntimeState(): StagePerformanceRuntimeState {
  return {
    history: [],
    sequenceByPool: {},
    shuffleBags: {},
  };
}

export function createDefaultStagePerformancePool(
  characterId: string | undefined,
  trigger: StagePerformanceTrigger,
): StagePerformancePool {
  const entranceId = characterId === 'kurisu_fan'
    ? 'kurisu-lab-mem-004'
    : 'character-entrance';
  return {
    enabled: false,
    mode: 'shuffle',
    selectedIds: trigger === 'entrance' ? [entranceId] : [],
    avoidRecent: 1,
  };
}

export function getStagePerformancePresets(
  store: StagePerformanceStore,
): StagePerformancePreset[] {
  return [
    ...BUILTIN_STAGE_PERFORMANCES.map(cloneStagePerformancePreset),
    ...store.customPresets.map(cloneStagePerformancePreset),
  ];
}

export function cloneStagePerformancePreset(
  preset: StagePerformancePreset,
): StagePerformancePreset {
  return {
    ...preset,
    characterIds: preset.characterIds ? [...preset.characterIds] : undefined,
    triggers: [...preset.triggers],
    conditions: {
      keywords: [...preset.conditions.keywords],
      timePeriods: [...preset.conditions.timePeriods],
    },
  };
}

export function isStagePerformanceCompatible(
  preset: StagePerformancePreset,
  characterId: string | undefined,
  trigger: StagePerformanceTrigger,
): boolean {
  if (!preset.triggers.includes(trigger)) return false;
  if (!preset.characterIds?.length) return true;
  return Boolean(characterId && preset.characterIds.includes(characterId));
}

export function resolveStageTimePeriod(date: Date): StageTimePeriod {
  const hour = date.getHours();
  if (hour >= 5 && hour < 11) return 'morning';
  if (hour >= 11 && hour < 17) return 'day';
  if (hour >= 17 && hour < 22) return 'evening';
  return 'night';
}

function matchesConditions(
  preset: StagePerformancePreset,
  context: StagePerformanceSelectionContext,
): boolean {
  const normalizedText = (context.text || '').toLocaleLowerCase();
  if (
    preset.conditions.keywords.length > 0
    && !preset.conditions.keywords.some((keyword) => (
      normalizedText.includes(keyword.trim().toLocaleLowerCase())
    ))
  ) {
    return false;
  }

  if (
    preset.conditions.timePeriods.length > 0
    && !preset.conditions.timePeriods.includes(
      resolveStageTimePeriod(context.now || new Date()),
    )
  ) {
    return false;
  }
  return true;
}

function recentIdsForPool(
  state: StagePerformanceRuntimeState,
  trigger: StagePerformanceTrigger,
  count: number,
): string[] {
  if (count <= 0) return [];
  return state.history
    .filter((entry) => entry.trigger === trigger)
    .slice(-count)
    .map((entry) => entry.presetId);
}

function removeRecentlyPlayed(
  presets: StagePerformancePreset[],
  recentIds: string[],
): StagePerformancePreset[] {
  const withoutRecent = presets.filter((preset) => !recentIds.includes(preset.id));
  return withoutRecent.length > 0 ? withoutRecent : presets;
}

function shuffle<T>(items: T[], random: () => number): T[] {
  const result = [...items];
  for (let index = result.length - 1; index > 0; index -= 1) {
    const target = Math.floor(random() * (index + 1));
    [result[index], result[target]] = [result[target], result[index]];
  }
  return result;
}

function chooseWeighted(
  presets: StagePerformancePreset[],
  random: () => number,
): StagePerformancePreset {
  const total = presets.reduce((sum, preset) => sum + Math.max(0.01, preset.weight), 0);
  let cursor = random() * total;
  for (const preset of presets) {
    cursor -= Math.max(0.01, preset.weight);
    if (cursor <= 0) return preset;
  }
  return presets[presets.length - 1];
}

function isCoolingDown(
  preset: StagePerformancePreset,
  state: StagePerformanceRuntimeState,
  nowMs: number,
): boolean {
  const latest = [...state.history]
    .reverse()
    .find((entry) => entry.presetId === preset.id);
  return Boolean(latest && nowMs - latest.playedAt < preset.cooldownMs);
}

export function stagePerformancePoolKey(
  characterId: string | undefined,
  trigger: StagePerformanceTrigger,
): string {
  return `${characterId || 'unknown'}::${trigger}`;
}

export function selectStagePerformance(
  presets: StagePerformancePreset[],
  pool: StagePerformancePool,
  context: StagePerformanceSelectionContext,
  state: StagePerformanceRuntimeState,
  options: {
    requestedPresetId?: string;
    random?: () => number;
    preview?: boolean;
  } = {},
): StagePerformancePreset | null {
  if (!pool.enabled && !options.preview) return null;
  const random = options.random || Math.random;
  const nowMs = (context.now || new Date()).getTime();
  let eligible = presets.filter((preset) => (
    pool.selectedIds.includes(preset.id)
    && isStagePerformanceCompatible(preset, context.characterId, context.trigger)
    && (options.preview || matchesConditions(preset, context))
    && (options.preview || !isCoolingDown(preset, state, nowMs))
  ));

  if (options.requestedPresetId) {
    const requested = eligible.find((preset) => preset.id === options.requestedPresetId);
    if (
      requested
      && (options.preview || random() <= Math.min(1, Math.max(0, requested.probability)))
    ) {
      return requested;
    }
  }
  if (pool.mode === 'ai') return null;

  eligible = eligible.filter((preset) => (
    options.preview || random() <= Math.min(1, Math.max(0, preset.probability))
  ));
  if (eligible.length === 0) return null;

  const key = stagePerformancePoolKey(context.characterId, context.trigger);

  if (pool.mode === 'fixed') return eligible[0];
  const recentIds = recentIdsForPool(state, context.trigger, pool.avoidRecent);
  const candidates = removeRecentlyPlayed(eligible, recentIds);
  if (pool.mode === 'sequence') {
    const position = state.sequenceByPool[key] || 0;
    state.sequenceByPool[key] = position + 1;
    return candidates[position % candidates.length];
  }
  if (pool.mode === 'weighted') return chooseWeighted(candidates, random);

  let bag = (state.shuffleBags[key] || [])
    .filter((id) => candidates.some((preset) => preset.id === id));
  if (bag.length === 0) {
    bag = shuffle(candidates.map((preset) => preset.id), random);
  }
  const selectedId = bag.shift();
  state.shuffleBags[key] = bag;
  return candidates.find((preset) => preset.id === selectedId) || candidates[0];
}

export function recordStagePerformancePlayed(
  state: StagePerformanceRuntimeState,
  presetId: string,
  trigger: StagePerformanceTrigger,
  playedAt = Date.now(),
): void {
  state.history.push({ presetId, trigger, playedAt });
  if (state.history.length > 50) {
    state.history.splice(0, state.history.length - 50);
  }
}

export function buildStageDirectorCandidates(
  presets: StagePerformancePreset[],
  pool: StagePerformancePool,
  characterId: string | undefined,
  trigger: StagePerformanceTrigger,
): StageDirectorCandidate[] {
  if (!pool.enabled || !['ai', 'hybrid'].includes(pool.mode)) return [];
  return presets
    .filter((preset) => (
      pool.selectedIds.includes(preset.id)
      && isStagePerformanceCompatible(preset, characterId, trigger)
    ))
    .map((preset) => ({
      id: preset.id,
      name: preset.name,
      description: preset.description,
      triggers: [...preset.triggers],
    }));
}
