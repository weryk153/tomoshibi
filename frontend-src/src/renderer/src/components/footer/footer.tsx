/* eslint-disable react/require-default-props */
import {
  Box, Button, Textarea, IconButton, HStack,
} from '@chakra-ui/react';
import { BsMicFill, BsMicMuteFill } from 'react-icons/bs';
import { IoHandRightSharp } from 'react-icons/io5';
import { FiChevronDown } from 'react-icons/fi';
import { LuSend } from 'react-icons/lu';
import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { footerStyles } from './footer-styles';
import AIStateIndicator from './ai-state-indicator';
import { useFooter } from '@/hooks/footer/use-footer';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';

// Type definitions
interface FooterProps {
  isCollapsed?: boolean
  onToggle?: () => void
}

interface ToggleButtonProps {
  isCollapsed: boolean
  onToggle?: () => void
}

interface ActionButtonsProps {
  micOn: boolean
  onMicToggle: () => void
  onInterrupt: () => void
  // 只有角色正在說話時打斷才有意義。沒有這個旗標的話，那顆黃色按鈕永遠亮著，
  // 跟麥克風的綠／紅一起在畫面上搶注意力，卻有大半時間根本沒有東西可以打斷。
  canInterrupt: boolean
}

interface MessageInputProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  onCompositionStart: () => void
  onCompositionEnd: () => void
  onSend: () => void | Promise<void>
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
      color="whiteAlpha.500"
      style={{
        transform: isCollapsed ? 'rotate(180deg)' : 'rotate(0deg)',
      }}
    >
      <FiChevronDown aria-hidden="true" />
    </Button>
  );
});

ToggleButton.displayName = 'ToggleButton';

const ActionButtons = memo(({
  micOn, onMicToggle, onInterrupt, canInterrupt,
}: ActionButtonsProps) => {
  const { t } = useTranslation();
  return (
    <HStack gap={2}>
      <IconButton
        aria-label={micOn ? t('footer.micOn') : t('footer.micOff')}
        title={micOn ? t('footer.micOn') : t('footer.micOff')}
        bg={micOn ? 'green.500' : 'red.500'}
        {...footerStyles.footer.actionButton}
        onClick={onMicToggle}
      >
        {micOn ? <BsMicFill /> : <BsMicMuteFill />}
      </IconButton>
      <IconButton
        aria-label={t('footer.interrupt')}
        title={t('footer.interrupt')}
        // 能打斷的時候才上色。不能打斷時仍然可按（按了是無害的 no-op），
        // 只是視覺上退到背景，不再假裝自己跟麥克風一樣重要。
        bg={canInterrupt ? 'yellow.500' : 'whiteAlpha.200'}
        color={canInterrupt ? 'black' : 'whiteAlpha.700'}
        transition="background-color 0.2s ease-out, color 0.2s ease-out"
        {...footerStyles.footer.actionButton}
        onClick={onInterrupt}
      >
        <IoHandRightSharp size="24" />
      </IconButton>
    </HStack>
  );
});

ActionButtons.displayName = 'ActionButtons';

const MessageInput = memo(({
  value,
  onChange,
  onKeyDown,
  onCompositionStart,
  onCompositionEnd,
  onSend,
}: MessageInputProps) => {
  const { t } = useTranslation();

  // 這裡原本是 ui/input-group（Chakra）。它支援 start/end 附加元素，但迴紋針
  // 移除之後就沒有任何附加元素了，剩下的作用只有 flex:1——換成一個 div。
  return (
    <div className="flex-1">
      {/* 這裡本來有一顆迴紋針按鈕，但它沒有 onClick，也沒有任何附加檔案的流程可
          以接——按下去毫無反應。一個看起來能點、點了什麼都不會發生的控制項，
          比沒有這個控制項更糟：使用者會以為是壞掉了。等真的做附加檔案再放回來。 */}
      <Box position="relative" width="100%">
        <Textarea
          value={value}
          onChange={onChange}
          onKeyDown={onKeyDown}
          onCompositionStart={onCompositionStart}
          onCompositionEnd={onCompositionEnd}
          placeholder={t('footer.typeYourMessage')}
          {...footerStyles.footer.input}
        />
        <IconButton
          aria-label={t('footer.send')}
          title={t('footer.send')}
          disabled={!value.trim()}
          onClick={onSend}
          {...footerStyles.footer.sendButton}
        >
          <LuSend size="20" aria-hidden="true" />
        </IconButton>
      </Box>
    </div>
  );
});

MessageInput.displayName = 'MessageInput';

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

  return (
    <Box {...footerStyles.footer.container(isCollapsed)}>
      <ToggleButton isCollapsed={isCollapsed} onToggle={onToggle} />

      <Box pt="0" px="4">
        <HStack width="100%" gap={4}>
          <Box>
            <Box mb="1.5">
              <AIStateIndicator />
            </Box>
            <ActionButtons
              micOn={micOn}
              onMicToggle={handleMicToggle}
              onInterrupt={handleInterrupt}
              canInterrupt={aiState === AiStateEnum.THINKING_SPEAKING}
            />
          </Box>

          <MessageInput
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyPress}
            onCompositionStart={handleCompositionStart}
            onCompositionEnd={handleCompositionEnd}
            onSend={handleSend}
          />
        </HStack>
      </Box>
    </Box>
  );
}

export default Footer;
