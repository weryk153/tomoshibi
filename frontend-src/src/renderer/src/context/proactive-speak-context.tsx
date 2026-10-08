import {
  createContext, useContext, ReactNode, useEffect, useRef, useCallback, useMemo,
} from 'react';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { useTriggerSpeak } from '@/hooks/utils/use-trigger-speak';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';
import { IS_STAGE } from '@/services/stage-mode';
import { useStream } from '@/context/stream-context';

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
  // also the gap between consecutive proactive turns. At a few seconds the
  // character talks over itself continuously — with no user turn in between,
  // each turn can only respond to the previous one.
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

    idleStartTimeRef.current = Date.now();
    const idleSeconds = Math.max(30, Number(settings.idleSecondsToSpeak) || 30);
    const tick = () => {
      const actualIdleTime = (Date.now() - idleStartTimeRef.current!) / 1000;
      sendTriggerSignal(actualIdleTime);
      // 後端可能這次不開口（角色設成「等你」時，沒人回就跳過幾次觸發）：她真的開口
      // 會換狀態、清掉這個計時器；沒開口就照樣再等一輪，不然計時器就此停住。
      idleTimerRef.current = setTimeout(tick, idleSeconds * 1000);
    };
    idleTimerRef.current = setTimeout(tick, idleSeconds * 1000);
  }, [settings.allowProactiveSpeak, settings.idleSecondsToSpeak, sendTriggerSignal, clearIdleTimer, live]);

  useEffect(() => {
    if (aiState === AiStateEnum.IDLE) {
      startIdleTimer();
    } else {
      clearIdleTimer();
    }
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
