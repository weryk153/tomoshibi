// 選裝套件沒裝時的一鍵安裝（目前是 faster-whisper，語音辨識頁用）。後端見
// optional_extras.py：用 uv 照鎖定清單裝，桌面版記住之後每次啟動一起同步。
// 裝好就重新載入，讓後端改用它（沒裝時後端會先退回 sherpa-onnx）。
import { useCallback, useEffect, useState } from 'react';
import { Stack, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { useWebSocket } from '@/context/websocket-context';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';
import { fetchExtraStatus, installExtra, lastLine, type ExtraStatus } from '@/api/extras';

type Phase = 'idle' | 'installing' | 'done' | 'error';

export function ExtraInstall({ name }: { name: string }): JSX.Element | null {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { reloadCharacter } = useSwitchCharacter();
  const [status, setStatus] = useState<ExtraStatus | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [line, setLine] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    fetchExtraStatus(baseUrl, name).then((result) => {
      if (!alive || !result.ok) return;
      setStatus(result.data);
      if (result.data.installing) setPhase('installing');
    });
    return () => { alive = false; };
  }, [baseUrl, name]);

  const install = useCallback(async () => {
    setPhase('installing');
    setError('');
    setLine('');
    let failed = '';
    const result = await installExtra(baseUrl, name, (event) => {
      setLine((previous) => lastLine(event, previous));
      if (event.status === 'error') failed = event.error || '';
    });
    if (!result.ok || failed) {
      setPhase('error');
      setError(failed || result.error || '');
      return;
    }
    setStatus((s) => (s ? { ...s, available: true } : s));
    setPhase('done');
    reloadCharacter();
  }, [baseUrl, name, reloadCharacter]);

  if (!status) return null;
  if (status.available && phase !== 'done') return null;

  return (
    <Stack gap={2}>
      {phase === 'done' ? (
        <Text fontSize="xs" color="green.300">{t(`settings.asr.extraInstalled_${name}`)}</Text>
      ) : (
        <>
          <Text fontSize="xs" color="orange.300">{t(`settings.asr.extraMissing_${name}`)}</Text>
          <div>
            <Button size="xs" variant="outline" loading={phase === 'installing'} onClick={() => { void install(); }}>
              {t('settings.asr.extraInstall', { name: 'faster-whisper', mb: status.download_mb })}
            </Button>
          </div>
          {phase === 'installing' && line && (
            <Text fontSize="xs" color="whiteAlpha.600" lineClamp={1}>{line}</Text>
          )}
          {phase === 'error' && (
            <Text fontSize="xs" color="red.300" whiteSpace="pre-wrap">{t('settings.asr.extraFailed', { error })}</Text>
          )}
        </>
      )}
    </Stack>
  );
}
