import { Box, Text } from '@chakra-ui/react';
import { memo } from 'react';
import { canvasStyles } from './canvas-styles';
import { useSubtitleDisplay } from '@/hooks/canvas/use-subtitle-display';
import { useSubtitle } from '@/context/subtitle-context';
import { collapseBlankLines } from '@/utils/collapse-blank-lines';

// Type definitions
interface SubtitleTextProps {
  text: string
}

// Reusable components
//
// 字幕樣式是 white-space: pre-wrap（canvas-styles.tsx），換行原樣保留——所以
// 文字裡的 '\n\n\n\n' 會變成三行高的空白，看起來像畫面壞掉或漏了一段。
// 這裡在渲染前收斂；為什麼修在這一層而不是後端，見 collapse-blank-lines.ts。
const SubtitleText = memo(({ text }: SubtitleTextProps) => (
  <Text {...canvasStyles.subtitle.text}>
    {collapseBlankLines(text)}
  </Text>
));

SubtitleText.displayName = 'SubtitleText';

// Main component
const Subtitle = memo((): JSX.Element | null => {
  const { subtitleText, isLoaded } = useSubtitleDisplay();
  const { showSubtitle } = useSubtitle();

  if (!isLoaded || !subtitleText || !showSubtitle) return null;

  return (
    <Box {...canvasStyles.subtitle.container}>
      <SubtitleText text={subtitleText} />
    </Box>
  );
});

Subtitle.displayName = 'Subtitle';

export default Subtitle;
