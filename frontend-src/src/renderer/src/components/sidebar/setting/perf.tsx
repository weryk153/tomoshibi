// perf 分頁：效能／硬體設定。跟 memory.tsx 一樣是無 props 的分頁（見
// setting-ui.tsx 的三處註冊）——存檔是即時打 API，不需要外層抽屜的
// Save/Cancel 去觸發。
//
// 一鍵效能模式（POST /api/perf/preset）只寫引擎背景工作的頻率與放在心上的
// 目標／想法數量，不碰語音辨識與聲音。選了就套用：隨時可以換回來，不用確認。
// 數字對不上任何模式時顯示「自訂」。
//
// 這個分頁不需要 useConfig()／confUid：這些設定存在 base conf.yaml，不是逐角色
// 檔案。
import {
  useState, useEffect, useCallback, useMemo,
} from 'react';
import { Stack, Text, Heading, Box } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useTranslation } from 'react-i18next';
import { settingStyles } from './setting-styles';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { SelectField } from './common';
import {
  fetchPerf,
  applyPreset,
  presetSelection,
  PRESET_CUSTOM,
  type PerfState,
} from '@/api/perf.ts';

// 一鍵模式的名稱／描述皆有專屬 i18n 鍵（不是後端傳什麼字串就原樣顯示），因為
// 後端的 key（light/standard/high）不是給使用者看的文案。找不到對應鍵時
// （理論上不會發生，presets 是後端 PRESETS 字典的 key）就直接顯示原始字串，
// 好過整個選項消失。
function presetNameKey(name: string): string | null {
  if (name === 'light') return 'settings.perf.presetLight';
  if (name === 'standard') return 'settings.perf.presetStandard';
  if (name === 'high') return 'settings.perf.presetHigh';
  if (name === PRESET_CUSTOM) return 'settings.perf.presetCustom';
  return null;
}

function presetDescKey(name: string): string | null {
  if (name === 'light') return 'settings.perf.presetLightDesc';
  if (name === 'standard') return 'settings.perf.presetStandardDesc';
  if (name === 'high') return 'settings.perf.presetHighDesc';
  return null;
}

function Perf(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();

  const [perf, setPerf] = useState<PerfState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);
  const [applyingPreset, setApplyingPreset] = useState(false);

  // 載入現值。refreshTick 讓套用 preset 成功後重新拉一次，顯示的模式才會跟著變。
  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    (async () => {
      const result = await fetchPerf(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setPerf(result.data);
      } else {
        setLoadError(result.error || t('settings.perf.loadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, refreshTick]);

  const current = presetSelection(perf?.current_preset, perf?.presets ?? []);

  // 「自訂」只在數字對不上任何模式時出現：它是狀態，不是一個可以套用的模式。
  const presetCollection = useMemo(() => createListCollection({
    items: [
      ...(perf?.presets ?? []),
      ...(current === PRESET_CUSTOM ? [PRESET_CUSTOM] : []),
    ].map((name) => {
      const key = presetNameKey(name);
      return { label: key ? t(key) : name, value: name };
    }),
  }), [perf?.presets, current, t]);

  const handlePresetChange = useCallback(async (value: string[]) => {
    const name = value[0];
    if (!name || name === PRESET_CUSTOM || name === current) return;
    setApplyingPreset(true);
    const result = await applyPreset(baseUrl, name);
    setApplyingPreset(false);
    if (result.ok) {
      const key = presetNameKey(name);
      toaster.create({
        title: t('settings.perf.applied', { name: key ? t(key) : name }),
        description: t('settings.perf.restartHint'),
        type: 'success',
        duration: 4000,
      });
      setRefreshTick((n) => n + 1);
    } else {
      toaster.create({
        title: result.error || t('settings.perf.applyFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, current, t]);

  if (loadError) {
    return (
      <Stack {...settingStyles.common.container}>
        <Text fontSize="sm" color="red.300">{loadError}</Text>
      </Stack>
    );
  }

  if (!perf) {
    return (
      <Stack {...settingStyles.common.container}>
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.perf.loading')}</Text>
      </Stack>
    );
  }

  const currentDescKey = presetDescKey(current);

  return (
    <Stack {...settingStyles.common.container} maxW="none">
      <Text fontSize="sm" color="whiteAlpha.700">{t('settings.perf.description')}</Text>

      <Stack gap={2}>
        <Heading size="sm">{t('settings.perf.presetSectionTitle')}</Heading>
        <Box opacity={applyingPreset ? 0.5 : 1} pointerEvents={applyingPreset ? 'none' : 'auto'}>
          <SelectField
            label={t('settings.perf.presetLabel')}
            value={[current]}
            onChange={handlePresetChange}
            collection={presetCollection}
            placeholder={t('settings.perf.presetPlaceholder')}
          />
        </Box>
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.perf.presetHelp')}</Text>
        {currentDescKey && (
          <Text fontSize="xs" color="whiteAlpha.700">{t(currentDescKey)}</Text>
        )}
      </Stack>
    </Stack>
  );
}

export default Perf;
