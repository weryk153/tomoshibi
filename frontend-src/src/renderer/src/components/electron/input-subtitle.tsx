import {
  LuBell, LuSend, LuMic, LuMicOff, LuHand, LuX,
} from 'react-icons/lu';
import {
  Box,
  Button,
  Flex,
  Input,
  Stack,
  Text,
  VStack,
  IconButton,
} from '@chakra-ui/react';
import { useState, useEffect, useCallback } from 'react';
import { useInputSubtitle } from '@/hooks/electron/use-input-subtitle';
import { useDraggable } from '@/hooks/electron/use-draggable';
import { inputSubtitleStyles } from './electron-style';
import { useTranslation } from 'react-i18next';
import { useMode } from '@/context/mode-context';

export function InputSubtitle() {
  const { t } = useTranslation();
  const {
    inputValue,
    handleInputChange,
    handleKeyPress,
    handleCompositionStart,
    handleCompositionEnd,
    handleInterrupt,
    handleMicToggle,
    handleSend,
    lastAIMessage,
    hasAIMessages,
    aiState,
    micOn,
  } = useInputSubtitle();

  const { mode } = useMode();
  const isPet = mode === 'pet';

  const {
    elementRef,
    isDragging,
    handleMouseDown,
    handleMouseEnter,
    handleMouseLeave,
  } = useDraggable({
    componentId: 'input-subtitle',
  });

  const [isVisible, setIsVisible] = useState(true);

  const handleClose = useCallback(() => {
    if (isPet) {
      (window.api as any)?.updateComponentHover('input-subtitle', false);
    }
    setIsVisible(false);
  }, [isPet]);

  const handleOpen = () => {
    setIsVisible(true);
  };

  useEffect(() => {
    if (isPet) {
      const cleanup = (window.api as any)?.onToggleInputSubtitle(() => {
        if (isVisible) {
          handleClose();
        } else {
          handleOpen();
        }
      });
      return () => cleanup?.();
    }
    return () => {};
  }, [handleClose, isPet, isVisible]);

  useEffect(() => {
    (window as any).inputSubtitle = {
      open: handleOpen,
      close: handleClose,
    };

    return () => {
      delete (window as any).inputSubtitle;
    };
  }, [isPet, handleClose]);

  if (!isVisible) return null;

  return (
    <Box
      ref={elementRef}
      {...inputSubtitleStyles.container}
      {...inputSubtitleStyles.draggableContainer(isDragging)}
      onMouseDown={handleMouseDown}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <Box {...inputSubtitleStyles.box}>
        <IconButton
          aria-label={t('window.closeSubtitle')}
          onClick={handleClose}
          {...inputSubtitleStyles.closeButton}
        >
          <LuX size={12} />
        </IconButton>

        {hasAIMessages && (
          <VStack
            minH={lastAIMessage ? '32px' : '0px'}
            {...inputSubtitleStyles.messageStack}
          >
            {lastAIMessage && (
              <Text {...inputSubtitleStyles.messageText}>
                {lastAIMessage}
              </Text>
            )}
          </VStack>
        )}

        <Box {...inputSubtitleStyles.statusBox}>
          <Flex align="center" justify="space-between" color="whiteAlpha.700">
            <Flex align="center" gap="2">
              <LuBell size={16} />
              {/* 桌寵模式以前直接印出 aiState 這個列舉值本身（畫面上會出現
                  thinking-speaking），視窗模式的同一個狀態卻是翻譯過的。
                  兩邊用同一組 aiState.* 鍵。 */}
              <Text {...inputSubtitleStyles.statusText}>
                {t(`aiState.${aiState}`)}
              </Text>
            </Flex>

            <Flex gap="2">
              <IconButton
                aria-label={micOn ? t('footer.micOn') : t('footer.micOff')}
                onClick={handleMicToggle}
                {...inputSubtitleStyles.iconButton}
              >
                {micOn ? <LuMic size={16} /> : <LuMicOff size={16} />}
              </IconButton>
              <IconButton
                aria-label={t('footer.interrupt')}
                onClick={handleInterrupt}
                {...inputSubtitleStyles.iconButton}
              >
                <LuHand size={16} />
              </IconButton>
            </Flex>
          </Flex>
        </Box>

        <Box {...inputSubtitleStyles.inputBox}>
          <Stack direction="row" gap="2" p="2">
            <Input
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleKeyPress}
              onCompositionStart={handleCompositionStart}
              onCompositionEnd={handleCompositionEnd}
              placeholder={t('footer.typeYourMessage')}
              {...inputSubtitleStyles.input}
            />
            <Button
              onClick={handleSend}
              {...inputSubtitleStyles.sendButton}
            >
              <LuSend size={16} />
            </Button>
          </Stack>
        </Box>
      </Box>
    </Box>
  );
}
