// perf 分頁：效能／硬體設定。跟 memory.tsx 一樣是無 props 的分頁（見
// setting-ui.tsx 的三處註冊）——存檔是即時打 API，不需要外層抽屜的
// Save/Cancel 去觸發。
//
// 兩個區塊，由上而下：一鍵效能模式（POST /api/perf/preset，原子寫入一組設定
// 葉）、模型保留時間（keep_alive 三選一）。
//
// 這個分頁不需要 useConfig()／confUid：這些設定存在 base conf.yaml，不是逐角色
// 檔案，perf_route.py 的寫入函式都沒有依 conf_uid 分流。
import {
  useState, useEffect, useCallback, useMemo,
} from 'react';
import { Stack, Text, Heading, HStack, Box } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useTranslation } from 'react-i18next';
import { settingStyles } from './setting-styles';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { SelectField, NumberField } from './common';
import {
  fetchPerf,
  setKeepAlive,
  applyPreset,
  keepAliveToMode,
  modeToKeepAlive,
  clampKeepAliveSeconds,
  KEEP_ALIVE_MAX,
  KEEP_ALIVE_SECONDS_MIN,
  type PerfState,
  type KeepAliveMode,
} from '@/api/perf.ts';

// keep_alive 的 UI 預設秒數草稿：使用者第一次把模式從永久常駐／立即卸載切到
// 「自訂秒數」時要有個起始值。跟後端 perf_route._keep_alive_from_conf 的
// 預設值一致（30 分鐘），不是隨便挑的數字。
const DEFAULT_KEEP_ALIVE_SECONDS_DRAFT = '1800';

// 一鍵模式的名稱／描述皆有專屬 i18n 鍵（不是後端傳什麼字串就原樣顯示），因為
// 後端的 key（light/standard/high）不是給使用者看的文案。找不到對應鍵時
// （理論上不會發生，presets 是後端 PRESETS 字典的 key）就直接顯示原始字串，
// 好過整個選項消失。
function presetNameKey(name: string): string | null {
  if (name === 'light') return 'settings.perf.presetLight';
  if (name === 'standard') return 'settings.perf.presetStandard';
  if (name === 'high') return 'settings.perf.presetHigh';
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

  // 一鍵效能模式。
  const [selectedPreset, setSelectedPreset] = useState('');
  const [pendingApplyPreset, setPendingApplyPreset] = useState(false);
  const [applyingPreset, setApplyingPreset] = useState(false);

  // 模型保留時間：模式（forever/immediate/seconds）＋自訂秒數草稿分開存。
  // 只有 modeToKeepAlive 能把這兩個值合成後端要的 KeepAliveValue——見
  // api/perf.ts 檔頭：這是刻意的型別品牌設計，擋掉「裸數字直接送出去」這條路，
  // 這裡的 UI 也照著這個分法走，不會有單一輸入框讓使用者打出 -1 或 0。
  const [keepAliveMode, setKeepAliveMode] = useState<KeepAliveMode>('immediate');
  const [keepAliveSecondsDraft, setKeepAliveSecondsDraft] = useState(
    DEFAULT_KEEP_ALIVE_SECONDS_DRAFT,
  );
  const [savingKeepAlive, setSavingKeepAlive] = useState(false);

  // 載入現值。refreshTick 讓套用 preset 成功後可以重新拉一次，兩個區塊都要
  // 反映新寫入的值。
  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    setPendingApplyPreset(false);
    (async () => {
      const result = await fetchPerf(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setPerf(result.data);
        const mode = keepAliveToMode(result.data.keep_alive);
        setKeepAliveMode(mode);
        if (mode === 'seconds') {
          setKeepAliveSecondsDraft(String(result.data.keep_alive));
        }
      } else {
        setLoadError(result.error || t('settings.perf.loadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, refreshTick]);

  const presetCollection = useMemo(() => createListCollection({
    items: (perf?.presets ?? []).map((name) => {
      const key = presetNameKey(name);
      return { label: key ? t(key) : name, value: name };
    }),
  }), [perf?.presets, t]);

  const keepAliveModeCollection = useMemo(() => createListCollection({
    items: [
      { label: t('settings.perf.keepAliveForever'), value: 'forever' },
      { label: t('settings.perf.keepAliveImmediate'), value: 'immediate' },
      { label: t('settings.perf.keepAliveCustom'), value: 'seconds' },
    ],
  }), [t]);

  const handleApplyPreset = useCallback(async () => {
    if (!selectedPreset) return;
    setApplyingPreset(true);
    const result = await applyPreset(baseUrl, selectedPreset);
    setApplyingPreset(false);
    setPendingApplyPreset(false);
    if (result.ok) {
      const key = presetNameKey(selectedPreset);
      toaster.create({
        title: t('settings.perf.applied', { name: key ? t(key) : selectedPreset }),
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
  }, [baseUrl, selectedPreset, t]);

  // 三選一模式切換：forever／immediate 立刻送出（沒有秒數可等使用者輸入）；
  // seconds 只切換畫面顯示秒數輸入框，等使用者按下面的儲存按鈕才送出——不然
  // 每次切到「自訂秒數」都會先用上一次的草稿值送一次，使用者根本還沒決定
  // 秒數是多少。
  const handleKeepAliveModeChange = useCallback(async (value: string[]) => {
    const mode = (value[0] ?? 'immediate') as KeepAliveMode;
    setKeepAliveMode(mode);
    if (mode === 'seconds') return;
    setSavingKeepAlive(true);
    const result = await setKeepAlive(baseUrl, modeToKeepAlive(mode, 0));
    setSavingKeepAlive(false);
    if (result.ok) {
      setPerf((p) => (p ? { ...p, keep_alive: mode === 'forever' ? -1 : 0 } : p));
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
  }, [baseUrl, t]);

  // 自訂秒數的儲存按鈕。clampKeepAliveSeconds 不接受字串（見 api/perf.ts
  // 檔頭），NumberField 給的 keepAliveSecondsDraft 是字串，這裡先用 Number()
  // 轉成數字再交給 modeToKeepAlive（它內部會再呼叫一次 clampKeepAliveSeconds）
  // ——直接把字串丟給 clampKeepAliveSeconds 會被 Number.isFinite('300') === false
  // 誤判成非法值，悄悄夾到下界 1，這是任務簡報點名過的陷阱。
  const handleKeepAliveSecondsSave = useCallback(async () => {
    const seconds = clampKeepAliveSeconds(Number(keepAliveSecondsDraft));
    setKeepAliveSecondsDraft(String(seconds));
    setSavingKeepAlive(true);
    const result = await setKeepAlive(baseUrl, modeToKeepAlive('seconds', seconds));
    setSavingKeepAlive(false);
    if (result.ok) {
      setPerf((p) => (p ? { ...p, keep_alive: seconds } : p));
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
  }, [baseUrl, keepAliveSecondsDraft, t]);

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

  const selectedPresetDescKey = selectedPreset ? presetDescKey(selectedPreset) : null;

  return (
    <Stack {...settingStyles.common.container} maxW="none">
      <Text fontSize="sm" color="whiteAlpha.700">{t('settings.perf.description')}</Text>

      {/* 一鍵效能模式：POST /api/perf/preset，一次原子寫入六個設定葉，跨
          ASR/TTS、記憶、keep_alive 三個區塊。這是不可逆的批次覆寫，所以按下
          「套用」不會立刻送出，先顯示確認區塊。 */}
      <Stack gap={2}>
        <Heading size="sm">{t('settings.perf.presetSectionTitle')}</Heading>
        <SelectField
          label={t('settings.perf.presetLabel')}
          value={selectedPreset ? [selectedPreset] : []}
          onChange={(value) => {
            setSelectedPreset(value[0] ?? '');
            setPendingApplyPreset(false);
          }}
          collection={presetCollection}
          placeholder={t('settings.perf.presetPlaceholder')}
        />
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.perf.presetHelp')}</Text>
        {/* 誠實揭露曾經做成一條額外的黃色警語（presetHighFasterWhisperNote），疊
            在 presetHighDesc 底下講「上面那句其實是錯的」。Review 抓到這樣兩句
            互相矛盾，使用者得自己判斷該信哪句，比只顯示其中一句還糟。正確做法
            是直接把 presetHighDesc 改成真的——見五語言 locale 檔案裡的新文案，
            這裡不再需要額外的揭露文字。 */}
        {selectedPresetDescKey && (
          <Text fontSize="xs" color="whiteAlpha.700">{t(selectedPresetDescKey)}</Text>
        )}
        {!pendingApplyPreset ? (
          <HStack>
            <Button
              size="xs"
              tone="blue"
              disabled={!selectedPreset}
              onClick={() => setPendingApplyPreset(true)}
            >
              {t('settings.perf.apply')}
            </Button>
          </HStack>
        ) : (
          <Box p={2} borderWidth="1px" borderColor="orange.700" borderRadius="sm">
            <Text fontSize="xs">{t('settings.perf.presetConfirm')}</Text>
            <HStack mt={2}>
              <Button
                size="xs"
                tone="blue"
                onClick={handleApplyPreset}
                loading={applyingPreset}
                loadingText={t('settings.perf.applying')}
              >
                {t('settings.characters.confirm')}
              </Button>
              <Button
                size="xs"
                variant="ghost"
                onClick={() => setPendingApplyPreset(false)}
                disabled={applyingPreset}
              >
                {t('common.cancel')}
              </Button>
            </HStack>
          </Box>
        )}
      </Stack>

      {/* 模型保留時間：三選一，不做裸數字輸入框。-1／0 是旗標不是秒數，只有
          modeToKeepAlive 能把「模式＋秒數」合成後端要的值——見 api/perf.ts
          檔頭與 handleKeepAliveModeChange／handleKeepAliveSecondsSave 旁的說明。 */}
      <Stack gap={2}>
        <Heading size="sm">{t('settings.perf.keepAliveSectionTitle')}</Heading>
        <SelectField
          label={t('settings.perf.keepAliveModeLabel')}
          value={[keepAliveMode]}
          onChange={handleKeepAliveModeChange}
          collection={keepAliveModeCollection}
          placeholder={t('settings.perf.keepAliveModePlaceholder')}
        />
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.perf.keepAliveHelp')}</Text>
        {keepAliveMode === 'seconds' && (
          <Stack gap={2}>
            <NumberField
              label={t('settings.perf.keepAliveLabel', {
                min: KEEP_ALIVE_SECONDS_MIN,
                max: KEEP_ALIVE_MAX,
              })}
              value={keepAliveSecondsDraft}
              onChange={setKeepAliveSecondsDraft}
              min={KEEP_ALIVE_SECONDS_MIN}
              max={KEEP_ALIVE_MAX}
              step={1}
            />
            <HStack>
              <Button
                size="xs"
                tone="blue"
                onClick={handleKeepAliveSecondsSave}
                loading={savingKeepAlive}
              >
                {t('common.save')}
              </Button>
            </HStack>
          </Stack>
        )}
      </Stack>
    </Stack>
  );
}

export default Perf;
