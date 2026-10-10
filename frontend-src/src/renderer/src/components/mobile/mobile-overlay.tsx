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
import { useSubtitle } from '@/context/subtitle-context';
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
    bg={active ? 'var(--moon-action)' : 'blackAlpha.500'}
    color={active ? 'var(--moon-action-ink)' : 'whiteAlpha.900'}
    _hover={{ bg: active ? 'var(--moon-action-hover)' : 'blackAlpha.700' }}
    fontSize="18px"
    {...rest}
  >
    {children}
  </Button>
));

RailButton.displayName = 'RailButton';

// 名字做成小標籤，配色照電腦版的聊天泡泡（她：--moon-bubble，我：--moon-user-bubble），
// 換主題也跟著變。直接當文字顏色的話，亮色主題兩種都太淡、疊在暗底上分不出來。
function NameTag({ name, mine }: { name: string, mine: boolean }): JSX.Element {
  return (
    <Text
      as="span"
      display="inline-block"
      fontSize="12px"
      fontWeight="600"
      lineHeight="1.4"
      px="1.5"
      mr="1.5"
      borderRadius="6px"
      textShadow="none"
      bg={mine ? 'var(--moon-user-bubble)' : 'var(--moon-bubble)'}
      border="1px solid"
      borderColor={mine ? 'var(--moon-user-line)' : 'var(--moon-bubble-line)'}
      color="var(--moon-ink)"
    >
      {name}
    </Text>
  );
}

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
        borderColor="var(--moon-purple)"
        borderRadius="10px"
        px="3"
        py="2"
      >
        <Box mb="1"><NameTag name={name} mine={false} /></Box>
        <Text fontSize="16.5px" lineHeight="1.5" fontWeight="500" color="white">{line.content}</Text>
      </Box>
    );
  }
  return (
    <Text fontSize="13px" lineHeight="1.45" color="whiteAlpha.800" textShadow="0 1px 2px rgba(0,0,0,.9)">
      <NameTag name={name} mine={line.role !== 'ai'} />
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
  const { subtitleText } = useSubtitle();
  const {
    settingsOpen, onSettingsOpen, onSettingsClose, createNewHistory,
  } = useSidebar();
  const {
    videoRef, error, isStreaming, stream, toggleCamera,
  } = useCameraPanel();
  const [chatOpen, setChatOpen] = useState(true);
  // 自己的鏡頭畫面點一下就收起來（鏡頭照樣開著，她照樣看得到）；右邊的鏡頭鍵
  // 亮著就代表還在拍。下次開鏡頭時再顯示。
  const [previewOpen, setPreviewOpen] = useState(true);
  useEffect(() => {
    if (isStreaming) setPreviewOpen(true);
  }, [isStreaming]);
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
  // 收起聊天時就是一般的字幕：只有她正在唸的那一句，不是整段回覆。
  const shown = chatOpen ? lines : [];

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
        // video 一直掛著、只切換顯示：srcObject 是掛上時設的，卸載再掛回來就黑掉。
        <Box
          as="button"
          aria-label={t('mobile.hidePreview')}
          title={t('mobile.hidePreview')}
          onClick={() => setPreviewOpen(false)}
          display={previewOpen ? 'block' : 'none'}
          position="absolute"
          top="12px"
          left="12px"
          pointerEvents="auto"
          p="0"
          bg="transparent"
          border="none"
        >
          <Box
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
          {/* key 帶上位置：語音轉文字的訊息可能拿到同一個 id，key 撞了 React 會把舊的
              那幾行留在畫面上。 */}
          {shown.map((line, index) => (
            <Line key={`${index}-${line.id}`} line={line} userName={userName} aiName={aiName} />
          ))}
          {!chatOpen && subtitleText && (
            <Line
              line={{ id: 'subtitle', role: 'ai', content: subtitleText, live: true }}
              userName={userName}
              aiName={aiName}
            />
          )}
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
