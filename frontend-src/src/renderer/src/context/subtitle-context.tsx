import {
  createContext, useState, useMemo, useContext, memo, useRef, useCallback, useEffect,
} from 'react';
import { useTranslation } from 'react-i18next';
import { resolveAutoClear, resolveConversationEndClear } from '@/utils/subtitle-autoclear';

/**
 * Subtitle context state interface
 * @interface SubtitleState
 */
interface SubtitleState {
  /** Current subtitle text */
  subtitleText: string

  /**
   * Set subtitle text.
   *
   * The字幕條 is shared by three different kinds of message: what the character
   * says, one-off system notices ("新對話已開始"), and errors (a VAD misfire).
   * Only the first should stay on screen — a notice or an error that never
   * clears sits over the character indefinitely, and the next thing the user
   * sees looks like something she said. Pass autoClearMs for the transient
   * kinds; omit it for speech.
   */
  setSubtitleText: (text: string, autoClearMs?: number) => void

  /**
   * Take the character's last spoken line down when she stops speaking.
   *
   * Speech subtitles deliberately have no autoClearMs — they must stay for as
   * long as the audio lasts, and nothing knows that duration up front. The end
   * of the conversation chain is that signal. Transient notices are left alone;
   * they own their own timers.
   */
  clearSpeechSubtitle: () => void

  /** Whether to show subtitle */
  showSubtitle: boolean

  /** Toggle subtitle visibility */
  setShowSubtitle: (show: boolean) => void
}

/**
 * Default values and constants
 */
// 上游留下來的英文玩笑話，會在連線完成前蓋在角色身上閃一下——這個專案的介面
// 是中文的，而且開場就用一段沒人寫過的台詞代替角色說話並不合理。留空：她還沒
// 開口以前，畫面上就不該有字幕條。
const DEFAULT_SUBTITLE = {
  text: '',
};

/**
 * Create the subtitle context
 */
export const SubtitleContext = createContext<SubtitleState | null>(null);

/**
 * Subtitle Provider Component
 * Manages the subtitle display text state
 *
 * @param {Object} props - Provider props
 * @param {React.ReactNode} props.children - Child components
 */
export const SubtitleProvider = memo(({ children }: { children: React.ReactNode }) => {
  // State management
  const { t } = useTranslation();
  const [subtitleText, setSubtitleTextState] = useState<string>(DEFAULT_SUBTITLE.text);
  const [showSubtitle, setShowSubtitle] = useState<boolean>(true);

  const clearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const setSubtitleText = useCallback((text: string, autoClearMs?: number) => {
    // 每次都先取消前一個計時器：不然一則「說完就消失」的通知排定的清除，會在
    // 使用者已經開始新對話之後才觸發，把角色正在講的話一起清掉。
    if (clearTimerRef.current) {
      clearTimeout(clearTimerRef.current);
      clearTimerRef.current = null;
    }
    setSubtitleTextState(text);
    if (autoClearMs && autoClearMs > 0) {
      clearTimerRef.current = setTimeout(() => {
        clearTimerRef.current = null;
        // 只清掉自己貼上去的那一則。中間如果已經換成別的內容（例如角色開口
        // 了），就不要動它——規則抽到 utils/subtitle-autoclear.ts 才測得到。
        setSubtitleTextState((current) => resolveAutoClear(current, text));
      }, autoClearMs);
    }
  }, []);

  const clearSpeechSubtitle = useCallback(() => {
    if (clearTimerRef.current) {
      clearTimeout(clearTimerRef.current);
      clearTimerRef.current = null;
    }
    const transient = new Set([
      t('notification.characterLoaded'),
      t('notification.newConversation'),
      t('subtitle.characterLoading'),
    ]);
    setSubtitleTextState((current) => resolveConversationEndClear(current, transient));
  }, [t]);

  useEffect(() => () => {
    if (clearTimerRef.current) clearTimeout(clearTimerRef.current);
  }, []);

  // Memoized context value
  const contextValue = useMemo(
    () => ({
      subtitleText,
      setSubtitleText,
      clearSpeechSubtitle,
      showSubtitle,
      setShowSubtitle,
    }),
    [subtitleText, setSubtitleText, clearSpeechSubtitle, showSubtitle],
  );

  return (
    <SubtitleContext.Provider value={contextValue}>
      {children}
    </SubtitleContext.Provider>
  );
});

/**
 * Custom hook to use the subtitle context
 * @throws {Error} If used outside of SubtitleProvider
 */
export function useSubtitle() {
  const context = useContext(SubtitleContext);

  if (!context) {
    throw new Error('useSubtitle must be used within a SubtitleProvider');
  }

  return context;
}
