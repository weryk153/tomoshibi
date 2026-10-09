import {
  forwardRef, useEffect, useMemo, useRef, useState,
} from 'react';
import { Box, Button, Text, type ButtonProps } from '@chakra-ui/react';
import {
  FiCamera, FiClock, FiMessageSquare, FiPlus, FiSettings,
} from 'react-icons/fi';
import { useTranslation } from 'react-i18next';
import Footer from '../footer/footer';
import HistoryDrawer from '../sidebar/history-drawer';
import SettingUI from '../sidebar/setting/setting-ui';
import { useSidebar } from '@/hooks/sidebar/use-sidebar';
import { useCameraPanel } from '@/hooks/sidebar/use-camera-panel';
import { useChatHistory } from '@/context/chat-history-context';
import { useConfig } from '@/context/character-config-context';
import { useAiState, AiStateEnum } from '@/context/ai-state-context';
import { toaster } from '@/components/ui/tw/toaster';
import { chatLines, type ChatLine } from './mobile-chat';

// 手機直式（窄螢幕）：像 YouTube 直式直播。角色滿版，聊天靠左疊在下方，
// 右緣一直排按鈕，輸入列在最底。沒有另外的字幕：她正在說的那一則就是字幕。

const CHAT_LIMIT = 30;

// forwardRef：紀錄按鈕是 HistoryDrawer 的 trigger（asChild），要接得到 ref 與事件。
const RailButton = forwardRef<HTMLButtonElement, ButtonProps & {
  label: string
  active?: boolean
}>(({ label, active = false, children, ...rest }, ref) => (
  <Button
    ref={ref}
    type="button"
    aria-label={label}
    title={label}
    aria-pressed={active}
    width="42px"
    height="42px"
    minW="42px"
    p="0"
    borderRadius="full"
    bg={active ? 'green.500' : 'blackAlpha.500'}
    color={active ? 'gray.950' : 'whiteAlpha.900'}
    _hover={{ bg: active ? 'green.400' : 'blackAlpha.700' }}
    fontSize="18px"
    {...rest}
  >
    {children}
  </Button>
));

RailButton.displayName = 'RailButton';

function Line({ line, userName, aiName }: {
  line: ChatLine
  userName: string
  aiName: string
}): JSX.Element {
  const name = line.role === 'ai' ? (line.name || aiName) : userName;
  if (line.live) {
    return (
      <Box
        bg="rgba(10, 10, 14, 0.72)"
        borderLeft="3px solid"
        borderColor="green.500"
        borderRadius="10px"
        px="3"
        py="2"
      >
        <Text fontSize="12px" fontWeight="600" color="blue.300" mb="0.5">{name}</Text>
        <Text fontSize="16.5px" lineHeight="1.5" fontWeight="500" color="white">{line.content}</Text>
      </Box>
    );
  }
  return (
    <Text fontSize="13px" lineHeight="1.45" color="whiteAlpha.800" textShadow="0 1px 2px rgba(0,0,0,.9)">
      <Text as="span" fontWeight="600" mr="1.5" color={line.role === 'ai' ? 'blue.300' : 'green.300'}>
        {name}
      </Text>
      {line.content}
    </Text>
  );
}

function readUserName(): string {
  try {
    const raw = window.localStorage.getItem('userDisplayName');
    const parsed = raw === null ? '' : JSON.parse(raw);
    return typeof parsed === 'string' ? parsed : '';
  } catch {
    return '';
  }
}

function MobileOverlay(): JSX.Element {
  const { t } = useTranslation();
  const { messages } = useChatHistory();
  const { confName } = useConfig();
  const { aiState } = useAiState();
  const {
    settingsOpen, onSettingsOpen, onSettingsClose, createNewHistory,
  } = useSidebar();
  const {
    videoRef, error, isStreaming, stream, toggleCamera,
  } = useCameraPanel();
  const [chatOpen, setChatOpen] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);

  const userName = readUserName() || t('sidebar.defaultUserName');
  const aiName = confName || 'AI';
  const lines = useMemo(
    () => chatLines(messages, {
      speaking: aiState === AiStateEnum.THINKING_SPEAKING,
      limit: CHAT_LIMIT,
    }),
    [messages, aiState],
  );
  // 收起聊天時只留她最後說的那一則（像字幕，說完還留著，直到下一句）。
  const last = lines[lines.length - 1];
  const shown = chatOpen
    ? lines
    : (last && last.role === 'ai' ? [{ ...last, live: true }] : []);

  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [shown]);

  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = stream;
  }, [stream, videoRef]);

  useEffect(() => {
    if (error) toaster.create({ title: error, type: 'error', duration: 4000 });
  }, [error]);

  return (
    <Box position="absolute" inset="0" zIndex={10} display="flex" flexDirection="column" pointerEvents="none">
      {/* 底部壓暗：只壓到聊天那一段，角色上半身保持原色。 */}
      <Box
        position="absolute"
        insetX="0"
        bottom="0"
        height="46%"
        bg="linear-gradient(transparent, rgba(0,0,0,.6) 55%, rgba(0,0,0,.75))"
      />

      {isStreaming && (
        <Box
          position="absolute"
          top="12px"
          left="12px"
          width="96px"
          aspectRatio="3 / 4"
          borderRadius="12px"
          overflow="hidden"
          border="2px solid"
          borderColor="whiteAlpha.400"
          bg="black"
        >
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)' }}
          />
        </Box>
      )}

      <Box flex="1" />

      <Box position="relative" display="flex" alignItems="flex-end" gap="2" px="3" pb="2">
        <Box
          ref={listRef}
          role="log"
          aria-live="polite"
          width="72%"
          maxH="34vh"
          overflowY="auto"
          display="flex"
          flexDirection="column"
          gap="1.5"
          pointerEvents="auto"
          css={{
            maskImage: 'linear-gradient(transparent, #000 22%)',
            WebkitMaskImage: 'linear-gradient(transparent, #000 22%)',
            scrollbarWidth: 'none',
          }}
        >
          {/* 第一則前面留白，淡出的遮罩才不會吃掉只有一兩則時的文字。 */}
          <Box flexShrink={0} height="4vh" />
          {shown.map((line) => (
            <Line key={line.id} line={line} userName={userName} aiName={aiName} />
          ))}
        </Box>

        <Box ml="auto" display="flex" flexDirection="column" gap="3" pointerEvents="auto">
          <RailButton
            label={t(chatOpen ? 'sidebar.collapsePanel' : 'sidebar.expandPanel')}
            active={chatOpen}
            onClick={() => setChatOpen(!chatOpen)}
          >
            <FiMessageSquare />
          </RailButton>
          <RailButton label={t('sidebar.camera')} active={isStreaming} onClick={toggleCamera}>
            <FiCamera />
          </RailButton>
          <RailButton label={t('sidebar.newChat')} onClick={createNewHistory}>
            <FiPlus />
          </RailButton>
          <HistoryDrawer>
            <RailButton label={t('sidebar.history')}>
              <FiClock />
            </RailButton>
          </HistoryDrawer>
          <RailButton label={t('common.settings')} onClick={onSettingsOpen}>
            <FiSettings />
          </RailButton>
        </Box>
      </Box>

      <Box pointerEvents="auto" position="relative">
        <Footer overlay />
      </Box>

      {settingsOpen && (
        <SettingUI open={settingsOpen} onClose={onSettingsClose} onToggle={onSettingsClose} />
      )}
    </Box>
  );
}

export default MobileOverlay;
