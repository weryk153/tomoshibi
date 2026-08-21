/* eslint-disable function-paren-newline */
/* eslint-disable react/jsx-one-expression-per-line */
/* eslint-disable no-trailing-spaces */
/* eslint-disable no-nested-ternary */
/* eslint-disable import/order */
/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable react/require-default-props */
import { useEffect, useState } from 'react';
import { Box, Spinner, Flex, Text, Icon } from '@chakra-ui/react';
import { sidebarStyles, chatPanelStyles } from './sidebar-styles';
import { MainContainer, ChatContainer, MessageList as ChatMessageList, Message as ChatMessage, Avatar as ChatAvatar } from '@chatscope/chat-ui-kit-react';
import '@chatscope/chat-ui-kit-styles/dist/default/styles.min.css';
import { useChatHistory } from '@/context/chat-history-context';
import { Global } from '@emotion/react';
import { useConfig } from '@/context/character-config-context';
import { useWebSocket } from '@/context/websocket-context';
import { FaTools, FaCheck, FaTimes, FaDownload } from 'react-icons/fa';
import { useTranslation } from 'react-i18next';

// 這兩個鍵由 you.tsx（設定 > 一般 > 「你」區塊）寫入，純 localStorage、沒有
// 後端端點。you.tsx 用的是 useLocalStorage（見 hooks/utils/use-local-storage.ts），
// 存的時候一律先 JSON.stringify，所以這裡讀也要對應 JSON.parse，不能直接把
// getItem 的結果當字串用（空字串會被存成 '""'）。
const USER_DISPLAY_NAME_KEY = 'userDisplayName';
const USER_AVATAR_KEY = 'userAvatarDataUrl';

function readLocalStorageString(key: string): string {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return '';
    const parsed = JSON.parse(raw);
    return typeof parsed === 'string' ? parsed : '';
  } catch {
    return '';
  }
}

// Main component
function ChatHistoryPanel(): JSX.Element {
  const { t } = useTranslation();
  const { messages } = useChatHistory(); // Get messages directly from context
  const { confName } = useConfig();
  const { baseUrl } = useWebSocket();

  // 初始值直接同步讀 localStorage（跟 useLocalStorage 的初始化方式一樣），
  // 之後靠 'storage' 事件更新——包含瀏覽器原生的跨分頁事件，以及 you.tsx
  // 在同一份文件內變更時手動 dispatch 的那一份（see you.tsx 檔頭註解，
  // 原生 'storage' 事件本來就不會在同一個 document 內自己觸發）。這裡不用
  // useLocalStorage 本身，因為它是各自獨立的 useState、不會互相通知；
  // 用事件監聽是不改共用 hook、只在需要反應的這兩個 component 之間搭橋的
  // 最小改法。
  const [userDisplayName, setUserDisplayName] = useState<string>(
    () => readLocalStorageString(USER_DISPLAY_NAME_KEY),
  );
  const [userAvatarDataUrl, setUserAvatarDataUrl] = useState<string>(
    () => readLocalStorageString(USER_AVATAR_KEY),
  );

  useEffect(() => {
    const handleStorage = (e: StorageEvent): void => {
      // e.key 是 null 代表 localStorage.clear()，兩個都要重讀。
      if (e.key === null || e.key === USER_DISPLAY_NAME_KEY) {
        setUserDisplayName(readLocalStorageString(USER_DISPLAY_NAME_KEY));
      }
      if (e.key === null || e.key === USER_AVATAR_KEY) {
        setUserAvatarDataUrl(readLocalStorageString(USER_AVATAR_KEY));
      }
    };
    window.addEventListener('storage', handleStorage);
    return (): void => window.removeEventListener('storage', handleStorage);
  }, []);

  // 沒設暱稱時的預設稱呼要跟著介面語言走——寫死成 'Me' 的話，中文介面的
  // 聊天紀錄裡自己的訊息會標成英文。
  const userName = userDisplayName || t('sidebar.defaultUserName');

  const validMessages = messages.filter((msg) => msg.content || // Keep messages with content
     (msg.type === 'tool_call_status' && msg.status === 'running') || // Keep running tools
     (msg.type === 'tool_call_status' && msg.status === 'completed') || // Keep completed tools
     (msg.type === 'tool_call_status' && msg.status === 'error'), // Keep error tools
  );

  return (
    <Box
      h="full"
      overflow="hidden"
      bg="gray.900"
    >
      <Global styles={chatPanelStyles} />
      <MainContainer>
        <ChatContainer>
          <ChatMessageList>
            {validMessages.length === 0 ? (
              <Box
                display="flex"
                alignItems="center"
                justifyContent="center"
                height="100%"
                color="whiteAlpha.500"
                fontSize="sm"
              >
                {t('sidebar.noMessages')}
              </Box>
            ) : (
              validMessages.map((msg) => {
                // Check if it's a tool call message
                if (msg.type === 'tool_call_status') {
                  return (
                    // Render Tool Call Indicator using msg properties
                    <Flex
                      key={msg.id} // Use tool_id as key
                      {...sidebarStyles.toolCallIndicator.container}
                      alignItems="center"
                    >
                      <Icon
                        as={FaTools}
                        {...sidebarStyles.toolCallIndicator.icon}
                      />
                      <Text {...sidebarStyles.toolCallIndicator.text}>
                        {/* {msg.tool_name}: {msg.status === 'running' ? 'Running...' : msg.content} */}
                        {msg.status === "running" ? `${msg.name} is using tool ${msg.tool_name}` : `${msg.name} used tool ${msg.tool_name}`}
                      </Text>
                      {/* Show spinner if running, checkmark if completed, maybe error icon? */}
                      {msg.status === "running" && (
                        <Spinner
                          size="xs"
                          color={sidebarStyles.toolCallIndicator.spinner.color}
                          ml={sidebarStyles.toolCallIndicator.spinner.ml}
                        />
                      )}
                      {msg.status === "completed" && (
                        <Icon
                          as={FaCheck}
                          {...sidebarStyles.toolCallIndicator.completedIcon}
                        />
                      )}
                      {/* Optional: Add an error icon */}
                      {msg.status === "error" && (
                        <Icon
                          as={FaTimes}
                          {...sidebarStyles.toolCallIndicator.errorIcon}
                        />
                      )}
                    </Flex>
                  );
                }
                if (msg.type === 'image' && msg.image) {
                  const imageUrl = `${baseUrl}${msg.image}`;
                  const fileName = msg.image.split('/').pop() || 'image.png';
                  return (
                    <Box key={msg.id} px={4} py={2}>
                      <img
                        src={imageUrl}
                        alt={msg.content}
                        style={{
                          maxWidth: '100%',
                          borderRadius: '8px',
                          display: 'block',
                        }}
                      />
                      <Flex alignItems="center" gap={2} mt={1}>
                        {/* 這個 Box 在 ChatMessage 之外，繼承不到聊天氣泡的
                            文字顏色，不指定就會是深色疊在深色面板上。跟隔壁
                            的 toolCallIndicator 用同一個色階。 */}
                        <Text fontSize="xs" color="whiteAlpha.700" flex="1">
                          {msg.content}
                        </Text>
                        {/* 桌面版的右鍵選單（menu-manager.ts）沒有「儲存圖片」，
                            所以不能只靠右鍵。圖片是後端同源提供的，download
                            屬性才會真的存檔而不是導頁。 */}
                        <a
                          href={imageUrl}
                          download={fileName}
                          title={t('history.downloadImage')}
                          aria-label={t('history.downloadImage')}
                          style={{ display: 'flex' }}
                        >
                          <Icon as={FaDownload} boxSize={3} color="whiteAlpha.700" />
                        </a>
                      </Flex>
                    </Box>
                  );
                }
                // Render Standard Chat Message (human or ai text)
                return (
                  <ChatMessage
                    key={msg.id}
                    model={{
                      message: msg.content,
                      sentTime: msg.timestamp,
                      sender: msg.role === 'ai'
                        ? (msg.name || confName || 'AI')
                        : userName,
                      direction: msg.role === 'ai' ? 'incoming' : 'outgoing',
                      position: 'single',
                    }}
                    avatarPosition={msg.role === 'ai' ? 'tl' : 'tr'}
                    avatarSpacer={false}
                  >
                    <ChatAvatar>
                      {msg.role === 'ai' ? (
                        msg.avatar ? (
                          <img
                            src={`${baseUrl}/avatars/${msg.avatar}`}
                            alt="avatar"
                            style={{
                              width: '100%',
                              height: '100%',
                              borderRadius: '50%',
                              // Character avatars are portrait crops (kurisu.png is
                              // 260x400), so the default object-fit: fill squashes the
                              // face sideways. Anchor to the top: a centred cover crop
                              // on a 2:3 portrait lands on the chest and cuts the head.
                              objectFit: 'cover',
                              objectPosition: 'top',
                            }}
                            onError={(e) => {
                              const target = e.target as HTMLImageElement;
                              const fallbackName = msg.name || confName || 'A';
                              target.outerHTML = `<div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; border-radius: 50%; background-color: var(--chakra-colors-blue-500); color: white; font-size: 14px;">${fallbackName[0].toUpperCase()}</div>`;
                            }}
                          />
                        ) : (
                          (msg.name && msg.name[0].toUpperCase()) ||
                            (confName && confName[0].toUpperCase()) ||
                            'A'
                        )
                      ) : userAvatarDataUrl ? (
                        <img
                          src={userAvatarDataUrl}
                          alt="avatar"
                          style={{ width: '100%', height: '100%', borderRadius: '50%', objectFit: 'cover' }}
                          onError={(e) => {
                            const target = e.target as HTMLImageElement;
                            target.outerHTML = `<div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; border-radius: 50%; background-color: var(--chakra-colors-blue-500); color: white; font-size: 14px;">${userName[0].toUpperCase()}</div>`;
                          }}
                        />
                      ) : (
                        userName[0].toUpperCase()
                      )}
                    </ChatAvatar>
                  </ChatMessage>
                );
              })
            )}
          </ChatMessageList>
        </ChatContainer>
      </MainContainer>
    </Box>
  );
}

export default ChatHistoryPanel;
