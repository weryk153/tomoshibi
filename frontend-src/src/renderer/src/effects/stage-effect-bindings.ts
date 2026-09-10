import type { StageEffectId } from './stage-effect.ts';

export const STAGE_MOTION_CUE_EVENT = 'tomoshibi:stage-motion-cue';
export const STAGE_INTERACTION_CUE_EVENT = 'tomoshibi:stage-interaction-cue';

// Cubism standardizes common parameter IDs, but not the meaning or names of
// complete character motions. These are Tomoshibi semantic action IDs; each
// character binding can map one to its own Cubism motion group/index.
export const STAGE_MOTION_ACTION_IDS = [
  'entrance',
  'greeting',
  'thinking',
  'surprised',
  'embarrassed',
  'laugh',
  'signature',
] as const;

export type StageMotionActionId = (typeof STAGE_MOTION_ACTION_IDS)[number];

export interface StageMotionCue {
  atMs: number;
  actionId: StageMotionActionId;
  group?: string;
  index?: number;
  priority: number;
}

export interface StageInteractionCue {
  atMs: number;
  action: 'cinematic-focus' | 'identity-scan' | 'impact' | 'release';
  intensity?: number;
  durationMs?: number;
}

export interface StageEffectPalette {
  primary: string;
  accent: string;
  glow: string;
  void: string;
}

export interface CharacterStageEffectBinding {
  title?: string;
  subtitle?: string;
  palette: StageEffectPalette;
  motionCues: StageMotionCue[];
  interactionCues: StageInteractionCue[];
  music?: {
    volume: number;
    fadeInMs: number;
    fadeOutMs: number;
    startAtMs: number;
  };
}

type CharacterBindings = Partial<Record<StageEffectId, CharacterStageEffectBinding>>;

export interface StageEffectCharacterInfo {
  name?: string;
  url?: string;
}

const DEFAULT_CINEMATIC_BURST: CharacterStageEffectBinding = {
  palette: {
    primary: '#d11f4d',
    accent: '#ffd37a',
    glow: '#ff8a3d',
    void: '#05030a',
  },
  motionCues: [],
  interactionCues: [
    {
      atMs: 180,
      action: 'cinematic-focus',
      intensity: 1,
      durationMs: 5100,
    },
    {
      atMs: 4100,
      action: 'impact',
      intensity: 1,
      durationMs: 600,
    },
    {
      atMs: 5550,
      action: 'release',
      durationMs: 650,
    },
  ],
};

const DEFAULT_CHARACTER_ENTRANCE: CharacterStageEffectBinding = {
  palette: {
    primary: '#b52249',
    accent: '#f2d5a2',
    glow: '#6fd7e5',
    void: '#070911',
  },
  motionCues: [],
  interactionCues: [
    {
      atMs: 120,
      action: 'cinematic-focus',
      intensity: 0.7,
      durationMs: 4000,
    },
    {
      atMs: 1650,
      action: 'identity-scan',
      intensity: 0.8,
      durationMs: 1250,
    },
    {
      atMs: 4200,
      action: 'release',
      durationMs: 600,
    },
  ],
};

// 人物專屬綁定。內建不帶任何人物，全部走通用演出；使用者替自己的角色設定的
// 綁定在執行期寫進這裡（見下方的 register 函式）。
const CHARACTER_BINDINGS: Record<string, CharacterBindings> = {};

function cloneBinding(binding: CharacterStageEffectBinding): CharacterStageEffectBinding {
  return {
    ...binding,
    palette: { ...binding.palette },
    motionCues: binding.motionCues.map((cue) => ({ ...cue })),
    interactionCues: binding.interactionCues.map((cue) => ({ ...cue })),
    music: binding.music ? { ...binding.music } : undefined,
  };
}

export function resolveStageEffectBinding(
  characterId: string | undefined,
  effectId: StageEffectId,
): CharacterStageEffectBinding {
  const characterBinding = characterId
    ? CHARACTER_BINDINGS[characterId]?.[effectId]
    : undefined;

  if (characterBinding) {
    return cloneBinding(characterBinding);
  }

  return cloneBinding(
    effectId === 'characterEntrance'
      ? DEFAULT_CHARACTER_ENTRANCE
      : DEFAULT_CINEMATIC_BURST,
  );
}

export function registerStageEffectBinding(
  characterId: string,
  effectId: StageEffectId,
  binding: CharacterStageEffectBinding,
): void {
  const normalizedCharacterId = characterId.trim();
  if (!normalizedCharacterId) {
    throw new Error('characterId is required');
  }
  CHARACTER_BINDINGS[normalizedCharacterId] = {
    ...CHARACTER_BINDINGS[normalizedCharacterId],
    [effectId]: cloneBinding(binding),
  };
}

export function resolveStageEffectCharacterId(
  modelInfo: StageEffectCharacterInfo | undefined,
): string | undefined {
  const explicitName = modelInfo?.name?.trim();
  if (explicitName) return explicitName;

  const url = modelInfo?.url?.split(/[?#]/, 1)[0] || '';
  const parts = url.split('/').filter(Boolean);
  const modelsIndex = parts.lastIndexOf('live2d-models');
  const directoryName = modelsIndex >= 0 ? parts[modelsIndex + 1] : undefined;
  return directoryName?.trim() || undefined;
}
