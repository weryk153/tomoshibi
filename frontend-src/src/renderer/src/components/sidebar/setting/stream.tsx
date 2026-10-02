// 直播分頁：貼直播網址、黑名單、冷場秒數，開始／停止，看狀態。
//
// 改了就存：文字停手 800ms 才送（不在打字途中改值）。狀態每 2 秒拉一次，只在這個
// 分頁看得到時拉。舞台頁網址照目前的後端位址組出來，貼到 OBS 的瀏覽器來源。
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Stack, Text, Heading, HStack } from '@chakra-ui/react';
import { settingStyles } from './setting-styles';
import { InputField, TextareaField } from './common';
import { Button, TextInput } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import {
  blocklistFromText, blocklistToText, fetchStream, parseQuietSeconds, saveStreamSettings,
  startBlockedKey, startStream, stopStream, type StreamSettings, type StreamStatus,
} from '@/api/stream.ts';

const SAVE_DELAY_MS = 800;
const POLL_MS = 2000;

interface StreamProps {
  active?: boolean;
}

// 值停止變動 SAVE_DELAY_MS 之後才存；載入完成前不存（enabled=false）。
function useDelayedSave(save: () => void, value: string, enabled: boolean): void {
  const saveRef = useRef(save);
  saveRef.current = save;
  useEffect(() => {
    if (!enabled) return undefined;
    const timer = setTimeout(() => saveRef.current(), SAVE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [value, enabled]);
}

function Stream({ active = true }: StreamProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const [saved, setSaved] = useState<StreamSettings | null>(null);
  const [status, setStatus] = useState<StreamStatus | null>(null);
  const [url, setUrl] = useState('');
  const [blocklist, setBlocklist] = useState('');
  const [quiet, setQuiet] = useState('');
  const [busy, setBusy] = useState(false);
  const loaded = useRef(false);

  const refresh = useCallback(async () => {
    const result = await fetchStream(baseUrl);
    if (!result.ok) return;
    setStatus(result.data.status);
    if (!loaded.current) {
      loaded.current = true;
      const s = result.data.settings;
      setSaved(s);
      setUrl(s.youtube_url);
      setBlocklist(blocklistToText(s.blocklist));
      setQuiet(String(s.quiet_seconds));
    }
  }, [baseUrl]);

  useEffect(() => {
    if (!active) return undefined;
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [active, refresh]);

  const save = useCallback(async (changes: Partial<StreamSettings>) => {
    const result = await saveStreamSettings(baseUrl, changes);
    if (result.ok) {
      setSaved(result.data.settings);
    } else {
      toaster.create({
        title: t('settings.stream.saveFailed'), description: result.error, type: 'error', duration: 3000,
      });
    }
  }, [baseUrl, t]);

  const ready = saved !== null;
  useDelayedSave(() => {
    if (saved && url.trim() !== saved.youtube_url) save({ youtube_url: url.trim() });
  }, url, ready);
  useDelayedSave(() => {
    const words = blocklistFromText(blocklist);
    if (saved && words.join('\n') !== saved.blocklist.join('\n')) save({ blocklist: words });
  }, blocklist, ready);
  useDelayedSave(() => {
    const seconds = parseQuietSeconds(quiet);
    if (saved && seconds !== null && seconds !== saved.quiet_seconds) save({ quiet_seconds: seconds });
  }, quiet, ready);

  const toggle = useCallback(async () => {
    if (!status) return;
    setBusy(true);
    const result = status.live ? await stopStream(baseUrl) : await startStream(baseUrl, url.trim());
    setBusy(false);
    if (result.ok) {
      setStatus(result.data);
    } else {
      toaster.create({
        title: t(`settings.stream.errors.${result.error}`, { defaultValue: result.error }),
        type: 'error',
        duration: 4000,
      });
      refresh();
    }
  }, [baseUrl, refresh, status, t, url]);

  const blockedKey = startBlockedKey(status, url);
  const stageUrl = `${baseUrl.replace(/\/+$/, '')}/?stage=1`;

  return (
    <Stack {...settingStyles.common.container} gap={3}>
      <Heading size="sm">{t('settings.stream.title')}</Heading>

      <Stack gap={1}>
        <Text fontSize="sm">{t('settings.stream.stageUrlLabel')}</Text>
        <TextInput readOnly value={stageUrl} onFocus={(e) => e.currentTarget.select()} />
        <Text fontSize="xs" color="whiteAlpha.700">{t('settings.stream.stageUrlHelp')}</Text>
      </Stack>

      <InputField
        label={t('settings.stream.urlLabel')}
        value={url}
        onChange={setUrl}
        placeholder="https://www.youtube.com/watch?v=..."
        help={t('settings.stream.urlHelp')}
        disabled={status?.live}
      />
      <TextareaField
        label={t('settings.stream.blocklistLabel')}
        value={blocklist}
        onChange={setBlocklist}
        rows={4}
        help={t('settings.stream.blocklistHelp')}
      />
      <InputField
        label={t('settings.stream.quietLabel')}
        value={quiet}
        onChange={setQuiet}
        type="number"
        help={t('settings.stream.quietHelp')}
      />

      <HStack>
        <Button
          size="sm"
          tone={status?.live ? 'red' : 'blue'}
          onClick={toggle}
          loading={busy}
          disabled={blockedKey !== null}
        >
          {status?.live ? t('settings.stream.stop') : t('settings.stream.start')}
        </Button>
        {blockedKey && <Text fontSize="xs" color="orange.300">{t(blockedKey)}</Text>}
      </HStack>

      {status && (
        <Stack gap={1} fontSize="sm">
          <Text>
            {status.stage_connected ? t('settings.stream.stageConnected') : t('settings.stream.stageMissing')}
            {' · '}
            {t(`settings.stream.chat.${status.chat}`)}
          </Text>
          <Text>
            {t('settings.stream.counts', { read: status.read, dropped: status.dropped, queued: status.queued })}
          </Text>
          {status.current && (
            <Text>{t('settings.stream.current', { author: status.current.author, text: status.current.text })}</Text>
          )}
          {!status.live && status.stopped_reason && (
            <Text color="orange.300">{t(`settings.stream.stopped.${status.stopped_reason}`)}</Text>
          )}
          {status.last_error && (
            <Text fontSize="xs" color="red.300">{t('settings.stream.lastError', { error: status.last_error })}</Text>
          )}
        </Stack>
      )}
    </Stack>
  );
}

export default Stream;
