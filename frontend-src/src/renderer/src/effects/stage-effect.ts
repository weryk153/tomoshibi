export const STAGE_EFFECT_IDS = ['characterEntrance', 'cinematicBurst'] as const;
export const STAGE_EFFECT_SCALES = ['accent', 'scene', 'cinematic'] as const;

export type StageEffectId = (typeof STAGE_EFFECT_IDS)[number];
export type StageEffectScale = (typeof STAGE_EFFECT_SCALES)[number];

export interface StageEffectOptions {
  title?: string;
  subtitle?: string;
  sound?: boolean;
  intensity?: number;
  characterId?: string;
  scale?: StageEffectScale;
  musicSlot?: string;
  musicVolume?: number;
  musicFadeInMs?: number;
  musicFadeOutMs?: number;
}

export interface NormalizedStageEffectOptions {
  title?: string;
  subtitle?: string;
  sound: boolean;
  intensity: number;
  characterId?: string;
  scale: StageEffectScale;
  musicSlot?: string;
  musicVolume: number;
  musicFadeInMs: number;
  musicFadeOutMs: number;
}

export interface StageEffectRequest {
  id: StageEffectId;
  options: NormalizedStageEffectOptions;
}

const EFFECT_DURATIONS: Record<StageEffectId, number> = {
  characterEntrance: 4800,
  cinematicBurst: 6200,
};

const EFFECT_DEFAULT_SCALES: Record<StageEffectId, StageEffectScale> = {
  characterEntrance: 'scene',
  cinematicBurst: 'cinematic',
};

export function isStageEffectId(value: unknown): value is StageEffectId {
  return typeof value === 'string'
    && STAGE_EFFECT_IDS.includes(value as StageEffectId);
}

export function isStageEffectScale(value: unknown): value is StageEffectScale {
  return typeof value === 'string'
    && STAGE_EFFECT_SCALES.includes(value as StageEffectScale);
}

export function normalizeStageEffectOptions(
  options: StageEffectOptions = {},
  defaultScale: StageEffectScale = 'scene',
): NormalizedStageEffectOptions {
  const requestedIntensity = Number(options.intensity ?? 1);
  const intensity = Number.isFinite(requestedIntensity)
    ? Math.min(1.5, Math.max(0.35, requestedIntensity))
    : 1;
  const requestedMusicVolume = Number(options.musicVolume ?? 0.5);
  const requestedFadeIn = Number(options.musicFadeInMs ?? 350);
  const requestedFadeOut = Number(options.musicFadeOutMs ?? 600);

  return {
    title: options.title?.trim() || undefined,
    subtitle: options.subtitle?.trim() || undefined,
    sound: options.sound ?? true,
    intensity,
    characterId: options.characterId?.trim() || undefined,
    scale: isStageEffectScale(options.scale) ? options.scale : defaultScale,
    musicSlot: options.musicSlot?.trim() || undefined,
    musicVolume: Number.isFinite(requestedMusicVolume)
      ? Math.min(1, Math.max(0, requestedMusicVolume))
      : 0.5,
    musicFadeInMs: Number.isFinite(requestedFadeIn)
      ? Math.max(0, requestedFadeIn)
      : 350,
    musicFadeOutMs: Number.isFinite(requestedFadeOut)
      ? Math.max(0, requestedFadeOut)
      : 600,
  };
}

export function getStageEffectDuration(id: StageEffectId): number {
  return EFFECT_DURATIONS[id];
}

export function createStageEffectRequest(
  id: StageEffectId,
  options: StageEffectOptions = {},
): StageEffectRequest {
  return {
    id,
    options: normalizeStageEffectOptions(options, EFFECT_DEFAULT_SCALES[id]),
  };
}
