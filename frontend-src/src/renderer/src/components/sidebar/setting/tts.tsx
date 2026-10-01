// tts 分頁：GPT-SoVITS 這個服務在哪、怎麼裝。
//
// 誰用哪個引擎、用哪段參考音、講哪種語言，是每個角色自己的設定，在角色頁改。
// 以前這一頁也能改引擎與參考音，寫的卻是底稿角色（conf.yaml），其他角色有自己
// 的設定時完全沒作用，使用者以為改了「全部」。
//
// 這個分頁本身不接 onSave／onCancel（跟 about.tsx 一樣是無 props 的分頁），
// 存檔即時發生、不受外層抽屜的 Save/Cancel 影響。
import { useState, useEffect, useCallback } from 'react';
import { Stack, Text, Heading, HStack } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { settingStyles } from './setting-styles';
import { InputField } from './common';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { fetchPerf, setTtsServiceUrl } from '@/api/perf.ts';
import GptSovitsInstall from '@/components/llm/gpt-sovits-install';

interface TTSProps {
  // 這個分頁目前是不是使用者看得到的那個 tab（setting-ui.tsx 依 activeTab
  // 算出）。切回來時重新拉一次現值：一鍵安裝會改服務位址。
  active?: boolean
}

function TTS({ active = true }: TTSProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();

  const [savedUrl, setSavedUrl] = useState<string | null>(null);
  const [draftUrl, setDraftUrl] = useState('');
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    (async () => {
      const result = await fetchPerf(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        const url = result.data.gpt_sovits_api_url || '';
        setSavedUrl(url);
        setDraftUrl(url);
        setLoadError(null);
      } else {
        setLoadError(result.error || t('settings.perf.loadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, active, refreshTick]);

  const handleSave = useCallback(async () => {
    const url = draftUrl.trim();
    if (!url) return;
    setSaving(true);
    const result = await setTtsServiceUrl(baseUrl, url);
    setSaving(false);
    if (result.ok) {
      setSavedUrl(result.data.gpt_sovits_api_url);
      setDraftUrl(result.data.gpt_sovits_api_url);
      toaster.create({
        title: t('settings.perf.saved'),
        description: t('settings.perf.restartHint'),
        type: 'success',
        duration: 4000,
      });
    } else {
      toaster.create({
        title: result.error || t('settings.perf.saveFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, draftUrl, t]);

  const unchanged = draftUrl.trim() === (savedUrl ?? '').trim();

  return (
    <Stack {...settingStyles.common.container} gap={2}>
      <Heading size="sm">{t('settings.perf.ttsSectionTitle')}</Heading>
      <Text fontSize="xs" color="blue.300">{t('settings.tts.voiceIsPerCharacter')}</Text>

      <GptSovitsInstall baseUrl={baseUrl} onInstalled={() => setRefreshTick((n) => n + 1)} />

      {loadError && (
        <Text fontSize="sm" color="red.300">{loadError}</Text>
      )}

      {savedUrl !== null && (
        <Stack gap={2}>
          <InputField
            label={t('settings.perf.gptSovitsApiUrlLabel')}
            value={draftUrl}
            onChange={setDraftUrl}
            placeholder="http://127.0.0.1:9880/tts"
            help={t('settings.perf.gptSovitsApiUrlHelp')}
          />
          <HStack>
            <Button
              size="xs"
              tone="blue"
              onClick={handleSave}
              loading={saving}
              disabled={!draftUrl.trim() || unchanged}
            >
              {t('common.save')}
            </Button>
          </HStack>
        </Stack>
      )}
    </Stack>
  );
}

export default TTS;
