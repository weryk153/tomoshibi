// 場景沒有可顯示的東西（網址空的、載入失敗、Live2D 場景的底）時的退路：預設背景圖。
// 背景由場景決定，這裡不再讀任何設定。
import { Box, Image } from '@chakra-ui/react';
import { memo } from 'react';
import { canvasStyles } from './canvas-styles';
import { useWebSocket } from '@/context/websocket-context';
import { DEFAULT_BACKGROUND_PATH, resolveSceneUrl } from '@/scenes/scene';

const Background = memo(({ children }: { children?: React.ReactNode }) => {
  const { baseUrl } = useWebSocket();
  return (
    <Box {...canvasStyles.background.container}>
      <Image
        {...canvasStyles.background.image}
        src={resolveSceneUrl(DEFAULT_BACKGROUND_PATH, baseUrl)}
        alt="background"
      />
      {children}
    </Box>
  );
});

Background.displayName = 'Background';

export default Background;
