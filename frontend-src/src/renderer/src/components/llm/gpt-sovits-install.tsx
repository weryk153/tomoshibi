/* eslint-disable import/no-extraneous-dependencies */
// 一鍵安裝 GPT-SoVITS（本機語音）。首次啟動精靈的最後一步，也放在語音設定分頁。
//
// 預設的 Edge TTS 已經能講話，這一步是加分，所以精靈裡一定有「先不要」。沒得裝
// （平台不支援、已經裝好、9880 已經有 GPT-SoVITS 在跑、查詢失敗）時精靈整步跳過，
// 設定分頁則整張卡片不顯示。
//
// Windows 要下載 8GB、裝十幾分鐘，不能把人卡在精靈裡：安裝中也可以先去聊天，串流
// 照樣在背景讀完。裝好時後端已經把語音切到 GPT-SoVITS，這裡請它重讀設定、不必
// 重啟——元件卸載了也一樣，reloadCharacter 走的是 app 層的連線。

import { useEffect, useRef, useState } from 'react';
import { Stack, Text, HStack } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import {
  describeEvent,
  fetchGptSovitsStatus,
  formatGb,
  installGptSovits,
  type GptSovitsStatus,
  type InstallStage,
} from '@/api/gpt-sovits.ts';

interface Props {
  baseUrl: string
  /** 精靈用：裝好、跳過、或沒得裝時往下走。沒給就是設定分頁的卡片，沒有「先不要」。 */
  onDone?: () => void
  /** 裝好之後呼叫。設定分頁用來重新讀取目前的引擎。 */
  onInstalled?: () => void
}

type Phase = 'idle' | 'running' | 'done' | 'error';

function GptSovitsInstall({ baseUrl, onDone, onInstalled }: Props): JSX.Element | null {
  const { t } = useTranslation();
  const { reloadCharacter } = useSwitchCharacter();
  const [status, setStatus] = useState<GptSovitsStatus | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [progress, setProgress] = useState<{ stage: InstallStage; percent: number | null } | null>(null);
  const [error, setError] = useState('');
  // 父元件每次渲染都給一個新的箭頭函式。放進 effect 的依賴會讓安裝中途重查狀態、
  // 看到「安裝中」又改畫面，所以用 ref 拿最新的那一個。
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchGptSovitsStatus(baseUrl);
      if (cancelled) return;
      const inWizard = onDoneRef.current !== undefined;
      const offer = result.ok
        && result.data.supported
        && !result.data.installed
        && !result.data.running
        && !(inWizard && result.data.installing);
      if (offer) setStatus(result.data);
      else onDoneRef.current?.();
    })();
    return () => {
      cancelled = true;
    };
  }, [baseUrl]);

  if (!status) return null;

  const install = async (): Promise<void> => {
    setPhase('running');
    setError('');
    setProgress({ stage: 'preparing', percent: null });
    const result = await installGptSovits(baseUrl, (event) => {
      const next = describeEvent(event);
      if (next) setProgress(next);
    });
    if (!result.ok) {
      setPhase('error');
      setError(result.error ?? '');
      return;
    }
    setPhase('done');
    reloadCharacter();
    onInstalled?.();
  };

  const progressText = (): string => {
    const percent = progress?.percent ?? 0;
    switch (progress?.stage) {
      case 'downloading': return t('setup.voiceDownloading', { percent });
      case 'extracting': return t('setup.voiceExtracting', { percent });
      case 'packages': return t('setup.voicePackages');
      case 'models': return t('setup.voiceModels');
      case 'voice': return t('setup.voiceReference');
      case 'starting': return t('setup.voiceStarting');
      case 'testing': return t('setup.voiceTesting');
      default: return t('setup.voicePreparing');
    }
  };

  const busyElsewhere = status.installing && phase === 'idle';

  return (
    <Stack gap={4}>
      <Stack gap={1}>
        {/* 設定分頁裡它是區塊標題底下的一張卡片，標題不能比區塊標題還大。 */}
        <Text fontWeight="bold" fontSize={onDone ? undefined : 'sm'}>{t('setup.voiceTitle')}</Text>
        <Text fontSize="sm" color="whiteAlpha.700">
          {t('setup.voiceIntro', {
            size: formatGb(status.download_bytes),
            disk: formatGb(status.required_free_bytes),
          })}
        </Text>
      </Stack>

      {busyElsewhere && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('setup.voiceBusy')}</Text>
      )}
      {phase === 'running' && (
        <Text fontSize="sm" color="whiteAlpha.700">{progressText()}</Text>
      )}
      {phase === 'error' && (
        <Text fontSize="sm" color="red.300">{t('setup.voiceFailed', { error })}</Text>
      )}

      {phase === 'done' ? (
        <Stack gap={2}>
          <Text fontSize="sm">{t('setup.voiceDone')}</Text>
          {onDone && (
            <Button tone="blue" onClick={onDone} className="self-start">
              {t('setup.voiceContinue')}
            </Button>
          )}
        </Stack>
      ) : (
        <HStack gap={3} flexWrap="wrap">
          {!busyElsewhere && (
            <Button tone="blue" disabled={phase === 'running'} onClick={install}>
              {phase === 'error' ? t('setup.voiceRetry') : t('setup.voiceInstall')}
            </Button>
          )}
          {onDone && (
            <Button variant="ghost" onClick={onDone}>
              {phase === 'running' ? t('setup.voiceBackground') : t('setup.voiceSkip')}
            </Button>
          )}
        </HStack>
      )}

      <Text fontSize="xs" color="whiteAlpha.600">{t('setup.voiceHelp')}</Text>
    </Stack>
  );
}

export default GptSovitsInstall;
