import { Box } from '@chakra-ui/react';
import React, { memo } from 'react';
import { useTranslation } from 'react-i18next';
import { canvasStyles } from './canvas-styles';
import { useWSStatus } from '@/hooks/canvas/use-ws-status';

// Type definitions
interface StatusContentProps {
  textKey: string
}

// Reusable components
const StatusContent: React.FC<StatusContentProps> = ({ textKey }) => {
  const { t } = useTranslation();
  return t(textKey);
};
const MemoizedStatusContent = memo(StatusContent);

// Main component
const WebSocketStatus = memo((): JSX.Element => {
  const {
    color, textKey, handleClick, isDisconnected, visible,
  } = useWSStatus();

  // 用透明度淡出而不是直接不渲染：狀態一變（例如斷線）要能立刻回來，
  // 中間不會有重新掛載造成的閃爍。pointerEvents 跟著關掉，隱形的時候
  // 不要擋住底下的畫布。
  return (
    <Box
      {...canvasStyles.wsStatus.container}
      opacity={visible ? 1 : 0}
      pointerEvents={visible ? 'auto' : 'none'}
      transition="opacity 0.4s ease"
      aria-hidden={!visible}
      backgroundColor={color}
      onClick={handleClick}
      cursor={isDisconnected ? 'pointer' : 'default'}
      _hover={{
        opacity: isDisconnected ? 0.8 : 1,
      }}
    >
      <MemoizedStatusContent textKey={textKey} />
    </Box>
  );
});

WebSocketStatus.displayName = 'WebSocketStatus';

export default WebSocketStatus;
