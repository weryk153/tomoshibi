/* eslint-disable react/require-default-props */
import {
  Box, Button, Textarea, IconButton,
} from '@chakra-ui/react';
import { BsMicFill, BsMicMuteFill } from 'react-icons/bs';
import { IoHandRightSharp } from 'react-icons/io5';
import { FiChevronDown } from 'react-icons/fi';
import { LuSend } from 'react-icons/lu';
import { memo, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { footerStyles } from './footer-styles';
import CharacterChip from './character-chip';
import { useFooter } from '@/hooks/footer/use-footer';
import { footerExtra } from '@/hooks/footer/footer-extra';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';
import { useStream } from '@/context/stream-context';
import { useProactiveSpeak } from '@/context/proactive-speak-context';

// Type definitions
interface FooterProps {
  isCollapsed?: boolean
  onToggle?: () => void
}

interface ToggleButtonProps {
  isCollapsed: boolean
  onToggle?: () => void
}

interface MicButtonProps {
  micOn: boolean
  onMicToggle: () => void
}

interface MessageInputProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  onCompositionStart: () => void
  onCompositionEnd: () => void
  onSend: () => void | Promise<void>
  onInterrupt: () => void
  // 她正在說話：打斷鍵出現，placeholder 改成「送出後會接著講」。
  speaking: boolean
  // 設定 > 代理「舉手按鈕提示她發言」開著時，不在說話也要有那顆鍵可按
  // （use-footer.ts 的 handleInterrupt 不在說話時走的就是這條）。
  allowRaiseHand: boolean
  // 直播中私人聊天暫停（後端也會擋）。
  disabled?: boolean
}

// Reusable components
const ToggleButton = memo(({ isCollapsed, onToggle }: ToggleButtonProps) => {
  const { t } = useTranslation();
  const label = t(isCollapsed ? 'footer.expandControls' : 'footer.collapseControls');
  return (
    <Button
      type="button"
      variant="ghost"
      {...footerStyles.footer.toggleButton}
      onClick={onToggle}
      aria-label={label}
      aria-expanded={!isCollapsed}
      title={label}
      style={{
        transform: isCollapsed ? 'rotate(180deg)' : 'rotate(0deg)',
      }}
    >
      <FiChevronDown aria-hidden="true" />
    </Button>
  );
});

ToggleButton.displayName = 'ToggleButton';

// 圓形開關：開＝主色描邊加光暈，關＝灰描邊加靜音圖示。不再是紅／綠方塊——
// 紅色留給錯誤，靜音不是錯誤。
const MicButton = memo(({ micOn, onMicToggle }: MicButtonProps) => {
  const { t } = useTranslation();
  const label = micOn ? t('footer.micOn') : t('footer.micOff');
  return (
    <IconButton
      aria-label={label}
      title={label}
      aria-pressed={micOn}
      {...footerStyles.footer.mic(micOn)}
      onClick={onMicToggle}
    >
      {micOn ? <BsMicFill size="18" /> : <BsMicMuteFill size="18" />}
    </IconButton>
  );
});

MicButton.displayName = 'MicButton';

const MessageInput = memo(({
  value,
  onChange,
  onKeyDown,
  onCompositionStart,
  onCompositionEnd,
  onSend,
  onInterrupt,
  speaking,
  allowRaiseHand,
  disabled = false,
}: MessageInputProps) => {
  const { t } = useTranslation();
  const hasText = value.trim() !== '';
  // 打斷鍵只在有東西可打斷時出現——原本那顆黃色方塊大半時間沒事可做，
  // 卻一直在畫面上搶注意力。
  const showHand = speaking || allowRaiseHand;
  const handLabel = speaking ? t('footer.interrupt') : t('footer.raiseHand');

  let placeholder = t('footer.typeYourMessage');
  if (disabled) placeholder = t('footer.streamingPaused');
  else if (speaking) placeholder = t('footer.queuedWhileSpeaking');

  // 這裡本來有一顆迴紋針按鈕，但它沒有 onClick，也沒有任何附加檔案的流程可
  // 以接——按下去毫無反應。等真的做附加檔案再放回來。
  return (
    <Box {...footerStyles.footer.inputSlot}>
      <Textarea
        rows={1}
        value={value}
        onChange={onChange}
        onKeyDown={onKeyDown}
        onCompositionStart={onCompositionStart}
        onCompositionEnd={onCompositionEnd}
        disabled={disabled}
        placeholder={placeholder}
        aria-label={t('footer.typeYourMessage')}
        {...footerStyles.footer.input(showHand)}
      />
      <Box {...footerStyles.footer.inlineButtons}>
        {showHand && (
          <IconButton
            aria-label={handLabel}
            title={handLabel}
            onClick={onInterrupt}
            {...footerStyles.footer.interruptButton}
          >
            <IoHandRightSharp size="15" aria-hidden="true" />
          </IconButton>
        )}
        <IconButton
          aria-label={t('footer.send')}
          title={t('footer.send')}
          disabled={disabled || !hasText}
          onClick={onSend}
          {...footerStyles.footer.sendButton(hasText)}
        >
          <LuSend size="16" aria-hidden="true" />
        </IconButton>
      </Box>
    </Box>
  );
});

MessageInput.displayName = 'MessageInput';

/**
 * 把面板往上長出來的高度寫進根節點的 --footer-extra，讓字幕（App.tsx）跟著
 * 往上讓開。寫在根節點而不是共同祖先：只有一個 footer，跟 App.tsx 的 --vh 同一種做法。
 */
function useFooterExtraVar(isCollapsed: boolean) {
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const panel = panelRef.current;
    const slot = panel?.parentElement;
    if (!panel || !slot) return undefined;
    const root = document.documentElement;
    const update = () => {
      const extra = footerExtra({
        panelHeight: panel.offsetHeight,
        slotHeight: slot.offsetHeight,
        collapsed: isCollapsed,
      });
      root.style.setProperty('--footer-extra', `${extra}px`);
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(panel);
    observer.observe(slot);
    return () => {
      observer.disconnect();
      root.style.removeProperty('--footer-extra');
    };
  }, [isCollapsed]);
  return panelRef;
}

// Main component
function Footer({ isCollapsed = false, onToggle }: FooterProps): JSX.Element {
  const {
    inputValue,
    handleInputChange,
    handleKeyPress,
    handleCompositionStart,
    handleCompositionEnd,
    handleSend,
    handleInterrupt,
    handleMicToggle,
    micOn,
  } = useFooter();
  const { aiState } = useAiState();
  const { live } = useStream();
  const { settings } = useProactiveSpeak();
  const panelRef = useFooterExtraVar(isCollapsed);

  return (
    <Box ref={panelRef} {...footerStyles.footer.container(isCollapsed)}>
      <ToggleButton isCollapsed={isCollapsed} onToggle={onToggle} />

      <Box {...footerStyles.footer.row}>
        <Box {...footerStyles.footer.lineSlot}>
          <CharacterChip />
        </Box>
        <Box {...footerStyles.footer.lineSlot}>
          <MicButton micOn={micOn} onMicToggle={handleMicToggle} />
        </Box>
        <MessageInput
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyPress}
          onCompositionStart={handleCompositionStart}
          onCompositionEnd={handleCompositionEnd}
          onSend={handleSend}
          onInterrupt={handleInterrupt}
          speaking={aiState === AiStateEnum.THINKING_SPEAKING}
          allowRaiseHand={settings.allowButtonTrigger}
          disabled={live}
        />
      </Box>
    </Box>
  );
}

export default Footer;
