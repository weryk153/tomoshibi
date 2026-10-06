import { Box, Text } from '@chakra-ui/react';
import { memo, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAiState } from '@/context/ai-state-context';
import { useConfig } from '@/context/character-config-context';
import {
  effectiveMood,
  getCharacterMood,
  onCharacterMoodChange,
  RESTING_REFRESH_MS,
} from '@/avatar/mood';
import { chipLabel, type ChipTone } from '@/hooks/footer/character-chip';
import { ACCENT_INK } from '@/theme/tomoshibi';

const FALLBACK_NAME = 'Tomoshibi';

const DOT_COLOR: Record<ChipTone, string> = {
  muted: 'gray.400',
  accent: 'green.500',
  accent2: 'blue.500',
  accentSoft: 'green.300',
  danger: 'red.400',
  busy: 'green.500',
};

/**
 * 她的心情（淡掉的強度也算進去）。心情一變就重算；沒變的時候每
 * RESTING_REFRESH_MS 重算一次，讓淡到門檻以下的心情回到「平靜」。
 */
function useCurrentMood() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const stop = onCharacterMoodChange(() => setNow(Date.now()));
    const timer = window.setInterval(() => setNow(Date.now()), RESTING_REFRESH_MS);
    return () => {
      stop();
      window.clearInterval(timer);
    };
  }, []);
  return effectiveMood(getCharacterMood(), now / 1000);
}

// 底部列左邊的角色膠囊：頭像色塊＋名字＋心情（忙的時候換成她在做什麼）。
// 原本左上角的 AIStateIndicator 徽章被它取代，所以 role="status"／aria-live
// 也在這裡——讀螢幕軟體靠它知道她在思考、說話還是聆聽。
function CharacterChip(): JSX.Element {
  const { t } = useTranslation();
  const { aiState } = useAiState();
  const { confName } = useConfig();
  const mood = useCurrentMood();
  const name = confName || FALLBACK_NAME;
  const label = chipLabel({
    aiState, mood: mood.mood, intensity: mood.intensity, t,
  });
  const busy = label.tone === 'busy';

  return (
    <Box
      display="flex"
      alignItems="center"
      gap="2.5"
      minW={0}
      maxW="220px"
      flexShrink={0}
      pl="1"
      pr="3"
      py="1"
      borderRadius="full"
      bg="gray.800"
      border="1px solid rgba(255, 255, 255, 0.07)"
    >
      <Box
        aria-hidden="true"
        width="36px"
        height="36px"
        minW="36px"
        borderRadius="full"
        bgGradient="to-br"
        gradientFrom="green.500"
        gradientTo="blue.500"
        display="flex"
        alignItems="center"
        justifyContent="center"
        color={ACCENT_INK}
        fontFamily="heading"
        fontWeight="700"
        fontSize="15px"
      >
        {Array.from(name)[0]?.toUpperCase()}
      </Box>
      <Box minW={0}>
        <Text
          fontFamily="heading"
          fontWeight="700"
          fontSize="14px"
          lineHeight="1.2"
          color="gray.50"
          truncate
        >
          {name}
        </Text>
        <Box
          display="flex"
          alignItems="center"
          gap="1.5"
          role="status"
          aria-live="polite"
        >
          <Box
            aria-hidden="true"
            width="6px"
            height="6px"
            minW="6px"
            borderRadius="full"
            bg={DOT_COLOR[label.tone]}
            animation={busy ? 'tmsbChipBeat 1s ease-in-out infinite' : undefined}
            _motionReduce={{ animation: 'none' }}
          />
          <Text
            fontFamily="mono"
            fontSize="11px"
            lineHeight="1.3"
            color="gray.400"
            truncate
          >
            {label.text}
          </Text>
        </Box>
      </Box>
    </Box>
  );
}

export default memo(CharacterChip);
