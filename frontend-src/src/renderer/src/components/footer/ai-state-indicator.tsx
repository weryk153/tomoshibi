import { Box, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useAiState } from '@/context/ai-state-context';
import { footerStyles } from './footer-styles';

function AIStateIndicator(): JSX.Element {
  const { t } = useTranslation();
  const { aiState } = useAiState();
  const styles = footerStyles.aiIndicator;

  return (
    <Box
      {...styles.container}
      bg={styles.stateColors[aiState] ?? styles.stateColors.idle}
      // 讀螢幕軟體看不到顏色，而這顆徽章是唯一告知目前狀態的地方。
      role="status"
      aria-live="polite"
    >
      <Text {...styles.text}>{t(`aiState.${aiState}`)}</Text>
    </Box>
  );
}

export default AIStateIndicator;
