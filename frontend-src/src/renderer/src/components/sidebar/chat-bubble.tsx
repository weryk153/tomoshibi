import { Box, Text, Flex } from '@chakra-ui/react';
import { Avatar as ArkAvatar } from '@ark-ui/react';
import { cx } from '@/components/ui/tw/primitives';
import { Message } from '@/services/websocket-service';

// Type definitions
interface ChatBubbleProps {
  message: Message;
  isSelected?: boolean;
  onClick?: () => void;
}

// Main component
export function ChatBubble({ message, isSelected, onClick }: ChatBubbleProps): JSX.Element {
  const isAI = message.role === 'ai';

  return (
    <Box
      onClick={onClick}
      cursor="pointer"
      bg={isSelected ? 'gray.100' : 'transparent'}
      _hover={{ bg: 'gray.50' }}
      p={2}
      borderRadius="md"
      transition="background-color 0.2s"
    >
      <Flex gap={3}>
        {/* Ark 的 Avatar 沒有 name→縮寫 的內建行為（Chakra 版有），縮寫在這裡
            自己算。沒有頭像圖片時 Fallback 一定會顯示，所以不需要條件判斷。 */}
        <ArkAvatar.Root
          className={cx(
            'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
            'text-xs font-semibold text-white',
            isAI ? 'bg-blue-500' : 'bg-green-500',
          )}
        >
          <ArkAvatar.Fallback>
            {(message.name || (isAI ? 'AI' : 'Me')).slice(0, 2)}
          </ArkAvatar.Fallback>
        </ArkAvatar.Root>
        <Box flex={1}>
          <Text fontSize="sm" fontWeight="bold" color="gray.700">
            {message.name || (isAI ? 'AI' : 'Me')}
          </Text>
          <Text
            fontSize="sm"
            color="gray.600"
            truncate
          >
            {message.content}
          </Text>
          <Text fontSize="xs" color="gray.400" mt={1}>
            {new Date(message.timestamp).toLocaleTimeString()}
          </Text>
        </Box>
      </Flex>
    </Box>
  );
}
