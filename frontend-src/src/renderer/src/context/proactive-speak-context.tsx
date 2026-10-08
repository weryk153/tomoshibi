import {
  createContext, useContext, ReactNode, useEffect, useRef, useCallback, useMemo,
} from 'react';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { useTriggerSpeak } from '@/hooks/utils/use-trigger-speak';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';
import { IS_STAGE } from '@/services/stage-mode';
import { useStream } from '@/context/stream-context';
import { nextProactiveDelay } from '@/utils/proactive-backoff';

interface ProactiveSpeakSettings {
  allowButtonTrigger: boolean;
  allowProactiveSpeak: boolean
  idleSecondsToSpeak: number
}

interface ProactiveSpeakContextType {
  settings: ProactiveSpeakSettings
  updateSettings: (newSettings: ProactiveSpeakSettings) => void
}

const defaultSettings: ProactiveSpeakSettings = {
  allowProactiveSpeak: false,
  // The timer restarts every time the character finishes speaking, so this is
  // also the gap before her first proactive turn. With no answer the gap
  // doubles each time and she stops after a few (utils/proactive-backoff): at
  // a fixed gap she talked over herself, taking her own last line for the
  // user's question.
  idleSecondsToSpeak: 120,
  allowButtonTrigger: false,
};

export const ProactiveSpeakContext = createContext<ProactiveSpeakContextType | null>(null);

export function ProactiveSpeakProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useLocalStorage<ProactiveSpeakSettings>(
    'proactiveSpeakSettings',
    defaultSettings,
  );

  const { aiState } = useAiState();
  const { live } = useStream();
  const { sendTriggerSignal } = useTriggerSpeak();

  const idleTimerRef = useRef<NodeJS.Timeout | null>(null);
  const idleStartTimeRef = useRef<number | null>(null);
  // 主動開口之後對方還沒回幾次（見 utils/proactive-backoff）；對方一開口就歸零。
  const unansweredRef = useRef(0);
  // 這一輪是不是我們觸發的主動開口（不是對方說話）。
  const ourTurnRef = useRef(false);

  const clearIdleTimer = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
    idleStartTimeRef.current = null;
  }, []);

  const startIdleTimer = useCallback(() => {
    clearIdleTimer();

    // 舞台頁什麼時候開口由直播模式決定，不跑自己的閒置計時器；直播中主視窗也不跑
    // （觸發會被後端擋掉，但擷取畫面這一步照樣會做）。
    if (IS_STAGE || live || !settings.allowProactiveSpeak) return;

    const idleSeconds = nextProactiveDelay(settings.idleSecondsToSpeak, unansweredRef.current);
    if (idleSeconds === null) return; // 連著好幾次沒人回：等對方開口

    idleStartTimeRef.current = Date.now();
    idleTimerRef.current = setTimeout(() => {
      const actualIdleTime = (Date.now() - idleStartTimeRef.current!) / 1000;
      ourTurnRef.current = true;
      unansweredRef.current += 1;
      sendTriggerSignal(actualIdleTime);
    }, idleSeconds * 1000);
  }, [settings.allowProactiveSpeak, settings.idleSecondsToSpeak, sendTriggerSignal, clearIdleTimer, live]);

  useEffect(() => {
    if (aiState === AiStateEnum.IDLE) {
      ourTurnRef.current = false;
      startIdleTimer();
      return;
    }
    clearIdleTimer();
    // 對方說話、打字、打斷她，或不是我們觸發的一輪：對方回了，重新算。
    const userActive = aiState === AiStateEnum.LISTENING
      || aiState === AiStateEnum.WAITING
      || aiState === AiStateEnum.INTERRUPTED
      || (aiState === AiStateEnum.THINKING_SPEAKING && !ourTurnRef.current);
    if (userActive) unansweredRef.current = 0;
  }, [aiState, startIdleTimer, clearIdleTimer]);

  useEffect(() => () => {
    clearIdleTimer();
  }, [clearIdleTimer]);

  const updateSettings = useCallback((newSettings: ProactiveSpeakSettings) => {
    setSettings(newSettings);
  }, [setSettings]);

  const contextValue = useMemo(() => ({
    settings,
    updateSettings,
  }), [settings, updateSettings]);

  return (
    <ProactiveSpeakContext.Provider value={contextValue}>
      {children}
    </ProactiveSpeakContext.Provider>
  );
}

export function useProactiveSpeak() {
  const context = useContext(ProactiveSpeakContext);
  if (!context) {
    throw new Error('useProactiveSpeak must be used within a ProactiveSpeakProvider');
  }
  return context;
}
