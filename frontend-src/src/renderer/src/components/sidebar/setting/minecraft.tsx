// Minecraft 分頁：MindServer 網址、機器人名字、閒置秒數、值得講的物品；開始／停止；看狀態。
//
// 跟直播分頁一樣：改了就存（useAutosave），狀態每 2 秒拉一次、只在分頁看得到時拉。
import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Stack, Text, Heading, HStack } from '@chakra-ui/react';
import { settingStyles } from './setting-styles';
import { InputField, TextareaField } from './common';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { boundsMessage } from '@/utils/setting-values';
import { useWebSocket } from '@/context/websocket-context';
import {
  fetchMinecraft, itemsToLines, linesToItems, parseSeconds, saveMinecraftSettings,
  startBlockedKey, startMinecraft, stopMinecraft, type MinecraftSettings, type MinecraftStatus,
} from '@/api/minecraft.ts';

const POLL_MS = 2000;
const IDLE_BOUNDS = { min: 3, max: 600, integer: true };

interface MinecraftProps {
  active?: boolean;
}

function Minecraft({ active = true }: MinecraftProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const [status, setStatus] = useState<MinecraftStatus | null>(null);
  const [url, setUrl] = useState('');
  const [botName, setBotName] = useState('');
  const [idle, setIdle] = useState('');
  const [items, setItems] = useState('');
  const [busy, setBusy] = useState(false);
  const loaded = useRef(false);

  const refresh = useCallback(async () => {
    const result = await fetchMinecraft(baseUrl);
    if (!result.ok) return;
    setStatus(result.data.status);
    if (!loaded.current) {
      loaded.current = true;
      const s = result.data.settings;
      setUrl(s.mindserver_url);
      setBotName(s.bot_name);
      setIdle(String(s.idle_seconds));
      setItems(itemsToLines(s.notable_items));
    }
  }, [baseUrl]);

  useEffect(() => {
    if (!active) return undefined;
    refresh();
    const timer = setInterval(refresh, POLL_MS);
    return () => clearInterval(timer);
  }, [active, refresh]);

  const save = useCallback(async (changes: Partial<MinecraftSettings>) => {
    const result = await saveMinecraftSettings(baseUrl, changes);
    if (!result.ok) return { ok: false, error: result.error } as const;
    return { ok: true } as const;
  }, [baseUrl]);

  const urlSaver = useAutosave((text: string) => save({ mindserver_url: text.trim() }));
  const nameSaver = useAutosave((text: string) => save({ bot_name: text.trim() }));
  const itemsSaver = useAutosave((text: string) => save({ notable_items: linesToItems(text) }));
  const idleSaver = useAutosave(
    (text: string) => save({ idle_seconds: parseSeconds(text, IDLE_BOUNDS.min, IDLE_BOUNDS.max) as number }),
    {
      validate: (text) => {
        if (parseSeconds(text, IDLE_BOUNDS.min, IDLE_BOUNDS.max) !== null) return null;
        const message = boundsMessage(IDLE_BOUNDS);
        return t(message.key, message.params);
      },
    },
  );

  const toggle = useCallback(async () => {
    if (!status) return;
    setBusy(true);
    const result = status.live ? await stopMinecraft(baseUrl) : await startMinecraft(baseUrl);
    setBusy(false);
    if (result.ok) {
      setStatus(result.data);
    } else {
      toaster.create({
        title: t(`settings.minecraft.errors.${result.error}`, { defaultValue: result.error }),
        type: 'error',
        duration: 4000,
      });
      refresh();
    }
  }, [baseUrl, refresh, status, t]);

  const blockedKey = startBlockedKey(status, botName);

  return (
    <Stack {...settingStyles.common.container} gap={3}>
      <Heading size="sm">{t('settings.minecraft.title')}</Heading>
      <Text fontSize="xs" color="whiteAlpha.700">{t('settings.minecraft.intro')}</Text>

      <InputField
        label={t('settings.minecraft.urlLabel')}
        value={url}
        onChange={(value) => { setUrl(value); urlSaver.change(value); }}
        onBlur={urlSaver.flush}
        placeholder="http://127.0.0.1:8080"
        disabled={status?.live}
      />
      <SaveStatus state={urlSaver.state} />
      <InputField
        label={t('settings.minecraft.botNameLabel')}
        value={botName}
        onChange={(value) => { setBotName(value); nameSaver.change(value); }}
        onBlur={nameSaver.flush}
        help={t('settings.minecraft.botNameHelp')}
        disabled={status?.live}
      />
      <SaveStatus state={nameSaver.state} />
      <InputField
        label={t('settings.minecraft.idleLabel')}
        value={idle}
        onChange={(value) => { setIdle(value); idleSaver.change(value); }}
        onBlur={idleSaver.flush}
        type="number"
        help={t('settings.minecraft.idleHelp')}
      />
      <SaveStatus state={idleSaver.state} />
      <TextareaField
        label={t('settings.minecraft.itemsLabel')}
        value={items}
        onChange={(value) => { setItems(value); itemsSaver.change(value); }}
        onBlur={itemsSaver.flush}
        rows={4}
        help={t('settings.minecraft.itemsHelp')}
      />
      <SaveStatus state={itemsSaver.state} />

      <HStack>
        <Button
          size="sm"
          tone={status?.live ? 'red' : 'blue'}
          onClick={toggle}
          loading={busy}
          disabled={blockedKey !== null}
        >
          {status?.live ? t('settings.minecraft.stop') : t('settings.minecraft.start')}
        </Button>
        {blockedKey && <Text fontSize="xs" color="orange.300">{t(blockedKey)}</Text>}
      </HStack>

      {status && (
        <Stack gap={1} fontSize="sm">
          <Text>
            {status.connected ? t('settings.minecraft.connected') : t('settings.minecraft.disconnected')}
            {' · '}
            {status.in_game ? t('settings.minecraft.inGame') : t('settings.minecraft.notInGame')}
          </Text>
          {status.health !== null && (
            <Text>{t('settings.minecraft.state', { health: status.health, action: status.action, pending: status.pending })}</Text>
          )}
          {!status.live && status.stopped_reason && (
            <Text color="orange.300">{t(`settings.minecraft.stopped.${status.stopped_reason}`)}</Text>
          )}
          {status.last_error && (
            <Text fontSize="xs" color="red.300">{t('settings.minecraft.lastError', { error: status.last_error })}</Text>
          )}
        </Stack>
      )}
    </Stack>
  );
}

export default Minecraft;
