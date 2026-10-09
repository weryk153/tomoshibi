/* eslint-disable react/require-default-props */
import {
  Box, Textarea, IconButton, VisuallyHidden,
} from '@chakra-ui/react';
import { BsMicFill, BsMicMuteFill } from 'react-icons/bs';
import { IoClose, IoHandRightSharp } from 'react-icons/io5';
import { LuSend } from 'react-icons/lu';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { footerStyles } from './footer-styles';
import CharacterChip from './character-chip';
import { useFooter } from '@/hooks/footer/use-footer';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';
import { useStream } from '@/context/stream-context';
import { useProactiveSpeak } from '@/context/proactive-speak-context';

// Type definitions
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
  // 有排隊中的訊息、輸入框是空的：送出鍵變成「現在送出」。
  hasQueued: boolean
  onSendQueuedNow: () => void
  onInterrupt: () => void
  // 她正在說話：打斷鍵出現、輸入框描邊亮起。placeholder 不換——空輸入框裡一句
  // 「她在說話…」讀起來像系統訊息（使用者反映很怪）；送出後排隊的事由字幕與她接著講來表示。
  speaking: boolean
  // 設定 > 代理「舉手按鈕提示她發言」開著時，不在說話也要有那顆鍵可按
  // （use-footer.ts 的 handleInterrupt 不在說話時走的就是這條）。
  allowRaiseHand: boolean
  // 直播中私人聊天暫停（後端也會擋）。
  disabled?: boolean
}

// Reusable components
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
  hasQueued,
  onSendQueuedNow,
  onInterrupt,
  speaking,
  allowRaiseHand,
  disabled = false,
}: MessageInputProps) => {
  const { t } = useTranslation();
  const hasText = value.trim() !== '';
  const sendNow = !hasText && hasQueued;
  // 打斷鍵只在有東西可打斷時出現——原本那顆黃色方塊大半時間沒事可做，
  // 卻一直在畫面上搶注意力。
  const showHand = speaking || allowRaiseHand;
  const handLabel = speaking ? t('footer.interrupt') : t('footer.raiseHand');

  const placeholder = disabled ? t('footer.streamingPaused') : t('footer.typeYourMessage');

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
          aria-label={sendNow ? t('footer.sendNow') : t('footer.send')}
          title={sendNow ? t('footer.sendNow') : t('footer.send')}
          disabled={disabled || (!hasText && !sendNow)}
          onClick={sendNow ? onSendQueuedNow : onSend}
          {...footerStyles.footer.sendButton(hasText || sendNow)}
        >
          <LuSend size="16" aria-hidden="true" />
        </IconButton>
      </Box>
    </Box>
  );
});

MessageInput.displayName = 'MessageInput';

function QueuedMessages({ items, onRemove }: {
  items: readonly string[]
  onRemove: (index: number) => void
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <Box display="flex" flexDirection="column" gap="4px" px="12px" pt="6px">
      <Box fontSize="xs" color="#80768d">{t('footer.queuedNote')}</Box>
      {items.map((text, index) => (
        <Box
          // 同一句可能排兩次，索引才分得開
          // eslint-disable-next-line react/no-array-index-key
          key={`${index}:${text}`}
          display="flex"
          alignItems="center"
          gap="6px"
          fontSize="sm"
          color="#80768d"
          bg="#f0eaf7"
          borderRadius="md"
          px="8px"
          py="4px"
        >
          <Box flex="1" whiteSpace="pre-wrap" wordBreak="break-word">{text}</Box>
          <IconButton
            aria-label={t('footer.cancelQueued')}
            title={t('footer.cancelQueued')}
            size="2xs"
            variant="ghost"
            onClick={() => onRemove(index)}
          >
            <IoClose aria-hidden="true" />
          </IconButton>
        </Box>
      ))}
    </Box>
  );
}

// Main component
interface FooterProps {
  /** 手機直式：半透明、疊在角色上。 */
  overlay?: boolean
}

function Footer({ overlay = false }: FooterProps): JSX.Element {
  const {
    inputValue,
    handleInputChange,
    handleKeyPress,
    handleCompositionStart,
    handleCompositionEnd,
    handleSend,
    handleInterrupt,
    handleSendQueuedNow,
    handleMicToggle,
    micOn,
    queued,
    removeQueued,
  } = useFooter();
  const { aiState } = useAiState();
  const { live } = useStream();
  const { settings } = useProactiveSpeak();

  return (
    // 右欄最底下的輸入列（像直播聊天室）。角色膠囊不顯示——心情與「思考、說話中」
    // 只留給讀螢幕軟體（膠囊裡的 role="status"），畫面上舞台與字幕已經看得出來。
    <Box {...(overlay ? footerStyles.footer.overlayContainer : footerStyles.footer.container)}>
      <VisuallyHidden>
        <CharacterChip />
      </VisuallyHidden>

      {/* 她講話時送出的訊息：排隊中，等她講完才真的送出、才進對話。 */}
      {queued.length > 0 && <QueuedMessages items={queued} onRemove={removeQueued} />}

      <Box {...footerStyles.footer.row}>
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
          hasQueued={queued.length > 0}
          onSendQueuedNow={handleSendQueuedNow}
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
