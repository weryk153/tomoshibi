import {
  createContext,
  useState,
  ReactNode,
  useContext,
  useCallback,
  useMemo,
  useRef,
  useEffect,
} from 'react';

/**
 * Enum for all possible AI states
 * @description Defines all possible states that the AI can be in
 */
// eslint-disable-next-line no-shadow
export const enum AiStateEnum {
  /**
   * - Can be triggered to speak proactively
   * - Ready to receive user input
   */
  IDLE = 'idle',

  /**
   * - Can be interrupted by user
   */
  THINKING_SPEAKING = 'thinking-speaking',

  /**
   * - Triggered by sending text / detecting speech / clicking interrupt button / creating new chat history / switching character
   */
  INTERRUPTED = 'interrupted',

  /**
   * - Shows during initial load / character switching
   */
  LOADING = 'loading',

  /**
   * - Speech is detected
   */
  LISTENING = 'listening',

  /**
   * - Set when user is typing
   * - Auto returns to IDLE after 2s
   */
  WAITING = 'waiting',
}

export type AiState = `${AiStateEnum}`;

/**
 * Type definition for the AI state context
 */
interface AiStateContextType {
  aiState: AiState;
  setAiState: {
    (state: AiState): void;
    (updater: (currentState: AiState) => AiState): void;
  };
  backendSynthComplete: boolean;
  setBackendSynthComplete: (complete: boolean) => void;
  isIdle: boolean;
  isThinkingSpeaking: boolean;
  isInterrupted: boolean;
  isLoading: boolean;
  isListening: boolean;
  isWaiting: boolean;
  resetState: () => void;
}

/**
 * Initial context value
 */
const initialState: AiState = AiStateEnum.LOADING;

/**
 * Create the AI state context
 */
export const AiStateContext = createContext<AiStateContextType | null>(null);

/**
 * AI State Provider Component
 */
export function AiStateProvider({ children }: { children: ReactNode }) {
  const [aiState, setAiStateInternal] = useState<AiState>(initialState);
  const [backendSynthComplete, setBackendSynthComplete] = useState(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // 目前狀態的即時鏡射。setAiState 的 updater 形式一定要拿到「現在」的狀態，
  // 而不是某次 render 閉包裡的舊值。
  //
  // 這在 conversation-chain-end 上出過事：那個處理器把 setAiState(updater) 包成
  // 一個 task 排進音訊佇列，等語音播完才執行——從排進去到真正執行之間隔了整段
  // 語音的時間，中間狀態早就換過好幾輪了。updater 拿到的卻是排隊當下那次
  // render 的 aiState，於是 `if (currentState === 'thinking-speaking')` 判斷失
  // 準，該轉回 idle 的沒轉，aiState 就永久停在 thinking-speaking：主動發言的閒
  // 置計時器只在 idle 才啟動，於是「允許主動發言」怎麼設都不會有反應。
  //
  // 用 ref 而不是把邏輯搬進 setAiStateInternal 的 updater：下面 WAITING 那條
  // 分支要排計時器，是副作用，不能寫在 React 的 updater 裡（StrictMode 會呼叫
  // 兩次）。附帶好處是 setAiState 的身分變成穩定的，依賴它的
  // handleControlMessage／handleWebSocketMessage 不會再每次狀態變動就重建。
  const aiStateRef = useRef<AiState>(initialState);

  const applyState = useCallback((next: AiState) => {
    aiStateRef.current = next;
    setAiStateInternal(next);
  }, []);

  const setAiState = useCallback((newState: AiState | ((currentState: AiState) => AiState)) => {
    const currentState = aiStateRef.current;
    const nextState = typeof newState === 'function'
      ? (newState as (currentState: AiState) => AiState)(currentState)
      : newState;

    if (nextState === AiStateEnum.WAITING) {
      if (currentState !== AiStateEnum.THINKING_SPEAKING) {
        applyState(nextState);

        if (timerRef.current) {
          clearTimeout(timerRef.current);
        }

        timerRef.current = setTimeout(() => {
          applyState(AiStateEnum.IDLE);
          timerRef.current = null;
        }, 2000);
      }
    } else {
      applyState(nextState);
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    }
  }, [applyState]);

  // Memoized state checks
  const stateChecks = useMemo(
    () => ({
      isIdle: aiState === AiStateEnum.IDLE,
      isThinkingSpeaking: aiState === AiStateEnum.THINKING_SPEAKING,
      isInterrupted: aiState === AiStateEnum.INTERRUPTED,
      isLoading: aiState === AiStateEnum.LOADING,
      isListening: aiState === AiStateEnum.LISTENING,
      isWaiting: aiState === AiStateEnum.WAITING,
    }),
    [aiState],
  );

  // Reset state handler
  const resetState = useCallback(() => {
    setAiState(AiStateEnum.IDLE);
  }, [setAiState]);

  useEffect(() => () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
  }, []);

  // Memoized context value
  const contextValue = useMemo(
    () => ({
      aiState,
      setAiState,
      backendSynthComplete,
      setBackendSynthComplete,
      ...stateChecks,
      resetState,
    }),
    [aiState, setAiState, backendSynthComplete, stateChecks, resetState],
  );

  return (
    <AiStateContext.Provider value={contextValue}>
      {children}
    </AiStateContext.Provider>
  );
}

/**
 * Custom hook to use the AI state context
 * @throws {Error} If used outside of AiStateProvider
 */
export function useAiState() {
  const context = useContext(AiStateContext);

  if (!context) {
    throw new Error('useAiState must be used within a AiStateProvider');
  }

  return context;
}
