import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  createStageEffectRequest,
  getStageEffectDuration,
  isStageEffectId,
  StageEffectId,
  StageEffectOptions,
  StageEffectRequest,
} from '@/effects/stage-effect';
import { playStageEffectSound } from '@/effects/stage-effect-audio';
import {
  CharacterStageEffectBinding,
  resolveStageEffectCharacterId,
  resolveStageEffectBinding,
  STAGE_INTERACTION_CUE_EVENT,
  STAGE_MOTION_CUE_EVENT,
} from '@/effects/stage-effect-bindings';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { stageEffectMusicPlayer } from '@/effects/stage-effect-music';

export const STAGE_EFFECT_EVENT = 'tomoshibi:stage-effect';

export interface ActiveStageEffect extends StageEffectRequest {
  sequence: number;
  characterId?: string;
  binding: CharacterStageEffectBinding;
}

interface StageEffectContextValue {
  activeEffect: ActiveStageEffect | null;
  playEffect: (id: StageEffectId, options?: StageEffectOptions) => void;
  stopEffect: () => void;
}

interface StageEffectEventDetail {
  id: StageEffectId;
  options?: StageEffectOptions;
}

const StageEffectContext = createContext<StageEffectContextValue | null>(null);

export function StageEffectProvider({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const [activeEffect, setActiveEffect] = useState<ActiveStageEffect | null>(null);
  const { modelInfo } = useLive2DConfig();
  const sequenceRef = useRef(0);
  const timeoutRefs = useRef<number[]>([]);

  const clearScheduledEvents = useCallback(() => {
    timeoutRefs.current.forEach((timeout) => window.clearTimeout(timeout));
    timeoutRefs.current = [];
  }, []);

  const stopEffect = useCallback(() => {
    clearScheduledEvents();
    stageEffectMusicPlayer.stop(
      activeEffect?.options.musicSlot
        ? activeEffect.options.musicFadeOutMs
        : activeEffect?.binding.music?.fadeOutMs,
    );
    if (activeEffect) {
      window.dispatchEvent(new CustomEvent(STAGE_INTERACTION_CUE_EVENT, {
        detail: {
          action: 'release',
          durationMs: 250,
          effectId: activeEffect.id,
          characterId: activeEffect.characterId,
        },
      }));
    }
    setActiveEffect(null);
  }, [activeEffect, clearScheduledEvents]);

  const playEffect = useCallback((
    id: StageEffectId,
    options: StageEffectOptions = {},
  ) => {
    clearScheduledEvents();
    stageEffectMusicPlayer.stop(180);
    if (activeEffect) {
      window.dispatchEvent(new CustomEvent(STAGE_INTERACTION_CUE_EVENT, {
        detail: {
          action: 'release',
          durationMs: 180,
          effectId: activeEffect.id,
          characterId: activeEffect.characterId,
        },
      }));
    }

    const request = createStageEffectRequest(id, options);
    const characterId = request.options.characterId
      || resolveStageEffectCharacterId(modelInfo);
    const binding = resolveStageEffectBinding(characterId, id);
    sequenceRef.current += 1;
    const sequence = sequenceRef.current;
    setActiveEffect({
      ...request,
      sequence,
      characterId,
      binding,
    });

    if (request.options.sound) {
      const playConfiguredAudio = async () => {
        let customMusicPlayed = false;
        const musicSlot = request.options.musicSlot || (binding.music ? id : undefined);
        const musicConfig = request.options.musicSlot
          ? {
            volume: request.options.musicVolume,
            fadeInMs: request.options.musicFadeInMs,
          }
          : binding.music;
        if (musicSlot && musicConfig && characterId) {
          customMusicPlayed = await stageEffectMusicPlayer.play(
            characterId,
            musicSlot,
            {
              volume: musicConfig.volume,
              fadeInMs: musicConfig.fadeInMs,
              fallbackSlotId: request.options.musicSlot ? id : undefined,
            },
          );
        }
        if (sequenceRef.current !== sequence) {
          return;
        }
        if (!customMusicPlayed) {
          playStageEffectSound(id, request.options.intensity);
        }
      };

      const startAtMs = request.options.musicSlot
        ? 0
        : binding.music?.startAtMs ?? 0;
      if (startAtMs > 0) {
        timeoutRefs.current.push(window.setTimeout(() => {
          playConfiguredAudio().catch((error) => {
            console.warn('[StageEffect] Could not start configured audio:', error);
          });
        }, startAtMs));
      } else {
        playConfiguredAudio().catch((error) => {
          console.warn('[StageEffect] Could not start configured audio:', error);
        });
      }
    }

    binding.motionCues.forEach((cue) => {
      timeoutRefs.current.push(window.setTimeout(() => {
        window.dispatchEvent(new CustomEvent(STAGE_MOTION_CUE_EVENT, {
          detail: {
            ...cue,
            effectId: id,
            characterId,
          },
        }));
      }, cue.atMs));
    });

    binding.interactionCues.forEach((cue) => {
      timeoutRefs.current.push(window.setTimeout(() => {
        window.dispatchEvent(new CustomEvent(STAGE_INTERACTION_CUE_EVENT, {
          detail: {
            ...cue,
            effectId: id,
            characterId,
          },
        }));
      }, cue.atMs));
    });

    timeoutRefs.current.push(window.setTimeout(() => {
      stageEffectMusicPlayer.stop(
        request.options.musicSlot
          ? request.options.musicFadeOutMs
          : binding.music?.fadeOutMs,
      );
      setActiveEffect((current) => (
        current?.sequence === sequence ? null : current
      ));
      timeoutRefs.current = [];
    }, getStageEffectDuration(id)));
  }, [activeEffect, clearScheduledEvents, modelInfo]);

  useEffect(() => {
    const handleStageEffect = (event: Event) => {
      const detail = (event as CustomEvent<StageEffectEventDetail>).detail;
      if (detail && isStageEffectId(detail.id)) {
        playEffect(detail.id, detail.options);
      }
    };

    window.addEventListener(STAGE_EFFECT_EVENT, handleStageEffect);
    window.TomoshibiEffects = {
      play: playEffect,
      stop: stopEffect,
      list: () => ['characterEntrance', 'cinematicBurst'],
    };

    return () => {
      window.removeEventListener(STAGE_EFFECT_EVENT, handleStageEffect);
      delete window.TomoshibiEffects;
      clearScheduledEvents();
      stageEffectMusicPlayer.stop(0);
    };
  }, [clearScheduledEvents, playEffect, stopEffect]);

  const value = useMemo(() => ({
    activeEffect,
    playEffect,
    stopEffect,
  }), [activeEffect, playEffect, stopEffect]);

  return (
    <StageEffectContext.Provider value={value}>
      {children}
    </StageEffectContext.Provider>
  );
}

export function useStageEffect(): StageEffectContextValue {
  const context = useContext(StageEffectContext);
  if (!context) {
    throw new Error('useStageEffect must be used within StageEffectProvider');
  }
  return context;
}
