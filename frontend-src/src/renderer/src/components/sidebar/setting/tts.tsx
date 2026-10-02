// tts 分頁：GPT-SoVITS 這個服務在哪、怎麼裝。
//
// 誰用哪個引擎、用哪段參考音、講哪種語言，是每個角色自己的設定，在角色頁改。
// 以前這一頁也能改引擎與參考音，寫的卻是底稿角色（conf.yaml），其他角色有自己
// 的設定時完全沒作用，使用者以為改了「全部」。
//
// 服務位址改了就存（停手或離開欄位）；要重新載入才生效，由抽屜頂端的提示處理。
import { useState, useEffect, useRef } from 'react';
import { Stack, Text, Heading } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { settingStyles } from './setting-styles';
import { InputField } from './common';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
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
  const savedUrlRef = useRef('');
  const [draftUrl, setDraftUrl] = useState('');
  const [loadError, setLoadError] = useState<string | null>(null);
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
        // 切回分頁會重抓：使用者正在改（草稿跟上次存的不一樣）就不蓋掉。
        setDraftUrl((draft) => (draft === '' || draft === savedUrlRef.current ? url : draft));
        savedUrlRef.current = url;
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

  const urlSaver = useAutosave(async (draft: string) => {
    const result = await setTtsServiceUrl(baseUrl, draft.trim());
    if (!result.ok) return { ok: false, error: result.error || t('settings.perf.saveFailed') } as const;
    setSavedUrl(result.data.gpt_sovits_api_url);
    savedUrlRef.current = result.data.gpt_sovits_api_url;
    return { ok: true } as const;
  }, { validate: (draft) => (draft.trim() ? null : t('settings.translator.endpointEmpty')) });


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
            onChange={(value) => { setDraftUrl(value); urlSaver.change(value); }}
            onBlur={urlSaver.flush}
            placeholder="http://127.0.0.1:9880/tts"
            help={t('settings.perf.gptSovitsApiUrlHelp')}
          />
          <SaveStatus state={urlSaver.state} />
        </Stack>
      )}
    </Stack>
  );
}

export default TTS;
