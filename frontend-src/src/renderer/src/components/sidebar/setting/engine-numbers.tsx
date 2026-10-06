// 效能頁的「背景工作頻率」：情緒、回話自檢、記憶、她自己的事、她的心情、目標、反思每幾輪跑一次，
// 以及放在心上的目標／想法數量。從原本的「一般」分頁搬來。停手才存，打到一半
// 的值不存也不彈回；要重新載入才生效，由抽屜頂端的提示處理。
import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Stack, Text } from '@chakra-ui/react';
import { useWebSocket } from '@/context/websocket-context';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { boundsMessage, parseBoundedNumber, type Bounds } from '@/utils/setting-values';
import {
  fetchEngineSettings, saveEngineSettings, type EngineSettings, type EngineEvery,
} from '@/api/agent-config.ts';
import { NumberField } from './common';

const EVERY_BOUNDS: Bounds = { min: 0, max: 99, integer: true };
const EVERY_KEYS: EngineEvery[] = [
  'emotion_every', 'reply_check_every', 'memory_every', 'self_memory_every', 'mood_every', 'goal_every',
  'reflection_every',
];
const SHOWN_KEYS: EngineEvery[] = ['goals_shown', 'thoughts_shown'];

function EngineNumbers(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const [engine, setEngine] = useState<EngineSettings | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [everyDrafts, setEveryDrafts] = useState<Record<EngineEvery, string> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchEngineSettings(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setEngine(result.data);
        setEveryDrafts({
          emotion_every: String(result.data.emotion_every),
          reply_check_every: String(result.data.reply_check_every),
          memory_every: String(result.data.memory_every),
          self_memory_every: String(result.data.self_memory_every),
          mood_every: String(result.data.mood_every),
          goal_every: String(result.data.goal_every),
          reflection_every: String(result.data.reflection_every),
          goals_shown: String(result.data.goals_shown),
          thoughts_shown: String(result.data.thoughts_shown),
        });
      } else {
        setEngineError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  const boundsText = (bounds: Bounds): string => {
    const message = boundsMessage(bounds);
    return t(message.key, message.params);
  };

  // 跟「後端最後一次確認存下的值」比，不跟畫面上一輪的 engine 比：上一筆剛存好、
  // 接著排的那筆在畫面重畫前就會跑，用 state 比會把「改回原值」誤判成沒變。
  const savedEngineRef = useRef<EngineSettings | null>(null);
  savedEngineRef.current = savedEngineRef.current ?? engine;
  const everySaver = useAutosave(async (drafts: Record<EngineEvery, string>) => {
    const saved = savedEngineRef.current;
    if (!saved) return { ok: true } as const;
    const changes: Partial<Record<EngineEvery, number>> = {};
    (Object.keys(drafts) as EngineEvery[]).forEach((key) => {
      const value = parseBoundedNumber(drafts[key], EVERY_BOUNDS);
      if (value !== null && value !== saved[key]) changes[key] = value;
    });
    if (Object.keys(changes).length === 0) return { ok: true } as const;
    const result = await saveEngineSettings(baseUrl, changes);
    if (!result.ok) return { ok: false, error: result.error } as const;
    savedEngineRef.current = { ...saved, ...result.data };
    setEngine((current) => (current ? { ...current, ...result.data } : current));
    return { ok: true } as const;
  }, {
    validate: (drafts) => (
      (Object.values(drafts) as string[]).some((v) => parseBoundedNumber(v, EVERY_BOUNDS) === null)
        ? boundsText(EVERY_BOUNDS)
        : null
    ),
  });

  const changeEvery = (key: EngineEvery, value: string): void => {
    if (!everyDrafts) return;
    const next = { ...everyDrafts, [key]: value };
    setEveryDrafts(next);
    everySaver.change(next);
  };

  const field = (key: EngineEvery): JSX.Element => (
    <NumberField
      key={key}
      label={t(`settings.general.engine_${key}`)}
      value={everyDrafts?.[key] ?? ''}
      min={0}
      max={99}
      step={1}
      onChange={(value) => changeEvery(key, value)}
      onBlur={everySaver.flush}
    />
  );

  return (
    <Stack gap={1}>
      {engineError && <Text fontSize="xs" color="red.300">{engineError}</Text>}
      {everyDrafts && (
        <>
          <Text fontSize="xs" color="whiteAlpha.600">{t('settings.general.engineEveryHelp')}</Text>
          {EVERY_KEYS.map(field)}
          <Text fontSize="xs" color="whiteAlpha.600">{t('settings.general.engineShownHelp')}</Text>
          {SHOWN_KEYS.map(field)}
          <SaveStatus state={everySaver.state} />
        </>
      )}
    </Stack>
  );
}

export default EngineNumbers;
