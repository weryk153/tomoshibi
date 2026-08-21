import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { useStageEffect } from '@/context/stage-effect-context';
import { useScene } from '@/context/scene-context';
import { getStageEffectDuration } from '@/effects/stage-effect';
import {
  buildStageDirectorCandidates,
  cloneStagePerformancePreset,
  createDefaultStagePerformancePool,
  createEmptyStagePerformanceStore,
  createStagePerformanceRuntimeState,
  getStagePerformancePresets,
  normalizeStagePerformanceStore,
  recordStagePerformancePlayed,
  selectStagePerformance,
  StagePerformancePool,
  StagePerformancePreset,
  StagePerformanceSelectionContext,
  StagePerformanceStore,
  StagePerformanceTrigger,
} from '@/effects/stage-performance';
import { resolveStageEffectCharacterId } from '@/effects/stage-effect-bindings';
import { wsService } from '@/services/websocket-service';

const STORAGE_KEY = 'tomoshibi-stage-performance-store-v1';

interface StagePerformanceContextValue {
  characterId?: string;
  presets: StagePerformancePreset[];
  getPool: (trigger: StagePerformanceTrigger) => StagePerformancePool;
  updatePool: (
    trigger: StagePerformanceTrigger,
    update: Partial<StagePerformancePool>,
  ) => void;
  duplicatePreset: (presetId: string) => string | null;
  updatePreset: (
    presetId: string,
    update: Partial<StagePerformancePreset>,
  ) => void;
  deletePreset: (presetId: string) => void;
  playPreset: (presetId: string) => boolean;
  playTrigger: (
    trigger: StagePerformanceTrigger,
    context?: Omit<StagePerformanceSelectionContext, 'trigger' | 'characterId'>,
    requestedPresetId?: string,
  ) => boolean;
  previewTrigger: (trigger: StagePerformanceTrigger) => boolean;
  syncAIDirector: () => void;
}

const StagePerformanceContext = createContext<StagePerformanceContextValue | null>(null);

function loadStore(): StagePerformanceStore {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value
      ? normalizeStagePerformanceStore(JSON.parse(value))
      : createEmptyStagePerformanceStore();
  } catch (error) {
    console.warn('[StagePerformance] Could not read saved performances:', error);
    return createEmptyStagePerformanceStore();
  }
}

function saveStore(store: StagePerformanceStore): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch (error) {
    console.warn('[StagePerformance] Could not save performances:', error);
  }
}

function createPresetId(name: string): string {
  const base = name.toLocaleLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 42) || 'performance';
  const suffix = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID().replace(/-/g, '').slice(0, 8)
    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`.slice(0, 8);
  return `${base}-${suffix}`;
}

export function StagePerformanceProvider({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const { modelInfo } = useLive2DConfig();
  const { playEffect } = useStageEffect();
  const { playPerformanceScene } = useScene();
  const [store, setStore] = useState<StagePerformanceStore>(loadStore);
  const runtimeRef = useRef(createStagePerformanceRuntimeState());
  const entranceTimerRef = useRef<number | null>(null);
  const entrancePlayedForRef = useRef<string | null>(null);
  const characterId = resolveStageEffectCharacterId(modelInfo);
  const presets = useMemo(() => getStagePerformancePresets(store), [store]);

  useEffect(() => saveStore(store), [store]);

  const getPool = useCallback((trigger: StagePerformanceTrigger) => {
    const key = characterId || 'unknown';
    return store.poolsByCharacter[key]?.[trigger]
      || createDefaultStagePerformancePool(characterId, trigger);
  }, [characterId, store.poolsByCharacter]);

  const updatePool = useCallback((
    trigger: StagePerformanceTrigger,
    update: Partial<StagePerformancePool>,
  ) => {
    const key = characterId || 'unknown';
    setStore((current) => {
      const previous = current.poolsByCharacter[key]?.[trigger]
        || createDefaultStagePerformancePool(characterId, trigger);
      return normalizeStagePerformanceStore({
        ...current,
        poolsByCharacter: {
          ...current.poolsByCharacter,
          [key]: {
            ...current.poolsByCharacter[key],
            [trigger]: {
              ...previous,
              ...update,
            },
          },
        },
      });
    });
  }, [characterId]);

  const duplicatePreset = useCallback((presetId: string): string | null => {
    const source = presets.find((preset) => preset.id === presetId);
    if (!source) return null;
    const id = createPresetId(source.name);
    const copy: StagePerformancePreset = {
      ...cloneStagePerformancePreset(source),
      id,
      builtin: false,
      name: `${source.name} Copy`,
    };
    setStore((current) => normalizeStagePerformanceStore({
      ...current,
      customPresets: [...current.customPresets, copy],
    }));
    return id;
  }, [presets]);

  const updatePreset = useCallback((
    presetId: string,
    update: Partial<StagePerformancePreset>,
  ) => {
    setStore((current) => normalizeStagePerformanceStore({
      ...current,
      customPresets: current.customPresets.map((preset) => (
        preset.id === presetId
          ? {
            ...preset,
            ...update,
            id: preset.id,
            builtin: false,
          }
          : preset
      )),
    }));
  }, []);

  const deletePreset = useCallback((presetId: string) => {
    setStore((current) => {
      const poolsByCharacter = Object.fromEntries(
        Object.entries(current.poolsByCharacter).map(([key, pools]) => [
          key,
          Object.fromEntries(
            Object.entries(pools).map(([trigger, pool]) => [
              trigger,
              {
                ...pool,
                selectedIds: pool.selectedIds.filter((id) => id !== presetId),
              },
            ]),
          ),
        ]),
      );
      return normalizeStagePerformanceStore({
        ...current,
        customPresets: current.customPresets.filter((preset) => preset.id !== presetId),
        poolsByCharacter,
      });
    });
  }, []);

  const startPreset = useCallback((
    preset: StagePerformancePreset,
    trigger: StagePerformanceTrigger,
  ) => {
    playEffect(preset.effectId, {
      characterId,
      scale: preset.scale,
      intensity: preset.intensity,
      sound: preset.sound,
      title: preset.title,
      subtitle: preset.subtitle,
      musicSlot: preset.id,
      musicVolume: preset.musicVolume,
      musicFadeInMs: preset.musicFadeInMs,
      musicFadeOutMs: preset.musicFadeOutMs,
    });
    playPerformanceScene(preset.id, getStageEffectDuration(preset.effectId));
    recordStagePerformancePlayed(runtimeRef.current, preset.id, trigger);
  }, [characterId, playEffect, playPerformanceScene]);

  const playPreset = useCallback((presetId: string): boolean => {
    const preset = presets.find((candidate) => candidate.id === presetId);
    if (!preset) return false;
    startPreset(preset, 'manual');
    return true;
  }, [presets, startPreset]);

  const playTrigger = useCallback((
    trigger: StagePerformanceTrigger,
    context: Omit<
      StagePerformanceSelectionContext,
      'trigger' | 'characterId'
    > = {},
    requestedPresetId?: string,
  ): boolean => {
    const selected = selectStagePerformance(
      presets,
      getPool(trigger),
      { ...context, characterId, trigger },
      runtimeRef.current,
      { requestedPresetId },
    );
    if (!selected) return false;
    startPreset(selected, trigger);
    return true;
  }, [characterId, getPool, presets, startPreset]);

  const previewTrigger = useCallback((trigger: StagePerformanceTrigger): boolean => {
    const selected = selectStagePerformance(
      presets,
      {
        ...getPool(trigger),
        enabled: true,
        mode: 'shuffle',
      },
      { characterId, trigger },
      runtimeRef.current,
      { preview: true },
    );
    if (!selected) return false;
    startPreset(selected, trigger);
    return true;
  }, [characterId, getPool, presets, startPreset]);

  const syncAIDirector = useCallback(() => {
    if (wsService.getCurrentState() !== 'OPEN') return;
    const candidatesById = new Map<string, ReturnType<
      typeof buildStageDirectorCandidates
    >[number] & { enabledContexts: StagePerformanceTrigger[] }>();
    (['conversation', 'proactive'] as const).forEach((trigger) => {
      buildStageDirectorCandidates(
        presets,
        getPool(trigger),
        characterId,
        trigger,
      ).forEach((candidate) => {
        const existing = candidatesById.get(candidate.id);
        if (existing) {
          if (!existing.enabledContexts.includes(trigger)) {
            existing.enabledContexts.push(trigger);
          }
          return;
        }
        candidatesById.set(candidate.id, {
          ...candidate,
          enabledContexts: [trigger],
        });
      });
    });
    const candidates = Array.from(candidatesById.values()).map((candidate) => ({
      id: candidate.id,
      name: candidate.name,
      description: `${candidate.description} Enabled for: ${
        candidate.enabledContexts.join(', ')
      }.`,
      triggers: candidate.triggers,
    }));
    wsService.sendMessage({
      type: 'configure-stage-director',
      candidates,
    });
  }, [characterId, getPool, presets]);

  useEffect(() => {
    const timer = window.setTimeout(syncAIDirector, 350);
    return () => window.clearTimeout(timer);
  }, [syncAIDirector]);

  useEffect(() => {
    const subscription = wsService.onStateChange((state) => {
      if (state === 'OPEN') {
        window.setTimeout(syncAIDirector, 500);
      }
    });
    return () => subscription.unsubscribe();
  }, [syncAIDirector]);

  useEffect(() => {
    if (entranceTimerRef.current !== null) {
      window.clearTimeout(entranceTimerRef.current);
    }
    if (
      !characterId
      || entrancePlayedForRef.current === characterId
      || !getPool('entrance').enabled
    ) {
      return undefined;
    }
    entranceTimerRef.current = window.setTimeout(() => {
      if (playTrigger('entrance')) {
        entrancePlayedForRef.current = characterId;
      }
      entranceTimerRef.current = null;
    }, 850);
    return () => {
      if (entranceTimerRef.current !== null) {
        window.clearTimeout(entranceTimerRef.current);
        entranceTimerRef.current = null;
      }
    };
  }, [characterId, getPool, playTrigger]);

  const value = useMemo<StagePerformanceContextValue>(() => ({
    characterId,
    presets,
    getPool,
    updatePool,
    duplicatePreset,
    updatePreset,
    deletePreset,
    playPreset,
    playTrigger,
    previewTrigger,
    syncAIDirector,
  }), [
    characterId,
    deletePreset,
    duplicatePreset,
    getPool,
    playPreset,
    playTrigger,
    presets,
    previewTrigger,
    syncAIDirector,
    updatePool,
    updatePreset,
  ]);

  return (
    <StagePerformanceContext.Provider value={value}>
      {children}
    </StagePerformanceContext.Provider>
  );
}

export function useStagePerformance(): StagePerformanceContextValue {
  const context = useContext(StagePerformanceContext);
  if (!context) {
    throw new Error('useStagePerformance must be used within StagePerformanceProvider');
  }
  return context;
}
