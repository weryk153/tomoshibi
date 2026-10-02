// 舞台頁的畫面（App.tsx 在 ?stage=1 時只渲染這個）。沒有側欄、底部、麥克風、首次設定
// 精靈；主動開口計時器在 proactive-speak-context 裡另外關掉。
import { Box, Text } from '@chakra-ui/react';
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Avatar } from '@/avatar/avatar';
import { useStageEffect } from '@/context/stage-effect-context';
import { useStream } from '@/context/stream-context';
import { stageBackgroundHidden } from '@/services/stage-mode';
import Scene from './scene';
import Subtitle from './subtitle';
import { StageEffects } from './stage-effects';

export default function StageView(): JSX.Element {
  const { t } = useTranslation();
  const { comment, stageReplaced } = useStream();
  const { activeEffect } = useStageEffect();
  const transparent = stageBackgroundHidden(window.location.search);

  useEffect(() => {
    if (!transparent) return;
    document.documentElement.style.background = 'transparent';
    document.body.style.background = 'transparent';
  }, [transparent]);

  return (
    <Box position="fixed" inset={0} overflow="hidden">
      {!transparent && (
        <Box position="absolute" inset={0}>
          <Scene />
        </Box>
      )}
      <Box
        position="absolute"
        inset={0}
        zIndex={5}
        data-stage-effect={activeEffect?.id}
        data-stage-effect-character={activeEffect?.characterId}
        data-stage-effect-scale={activeEffect?.options.scale}
      >
        <Avatar />
        <StageEffects />
      </Box>
      <Box
        position="absolute"
        bottom="40px"
        left="50%"
        transform="translateX(-50%)"
        width="70%"
        zIndex={10}
        display="flex"
        flexDirection="column"
        alignItems="center"
        gap={2}
      >
        {comment && (
          <Text
            fontSize="lg"
            color="whiteAlpha.900"
            bg="blackAlpha.600"
            px={3}
            py={1}
            borderRadius="md"
          >
            {`${comment.author}：${comment.text}`}
          </Text>
        )}
        <Subtitle />
      </Box>
      {stageReplaced && (
        <Box
          position="absolute"
          top="20px"
          left="50%"
          transform="translateX(-50%)"
          zIndex={20}
          bg="red.600"
          color="white"
          px={4}
          py={2}
          borderRadius="md"
        >
          {t('stream.stageReplaced')}
        </Box>
      )}
    </Box>
  );
}
