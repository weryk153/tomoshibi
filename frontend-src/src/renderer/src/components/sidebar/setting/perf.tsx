/* eslint-disable import/no-extraneous-dependencies */
// perf 分頁：效能／硬體設定。跟 memory.tsx 一樣是無 props 的分頁（見
// setting-ui.tsx 的三處註冊）——存檔是即時打 API，不需要外層抽屜的
// Save/Cancel 去觸發。
//
// 三個區塊，由上而下：一鍵效能模式（POST /api/perf/preset，原子寫入六個設定
// 葉）、模型保留時間（keep_alive 三選一）、記憶整理頻率（沿用 api/memory.ts
// 既有的 setMemoryConsolidation，見該檔案的說明：整理頻率的權威寫法在
// memory 命名空間，perf 命名空間的 /api/perf/consolidation 寫的是同一個
// 設定葉，這裡不重複包一份）。
//
// 這個分頁不需要 useConfig()／confUid：memory_consolidation_interval 存在
// base conf.yaml 的 character_config 底下，不是逐角色檔案，perf_route.py／
// memory_route.py 的寫入函式都沒有依 conf_uid 分流。setMemoryConsolidation
// 仍要求傳一個 conf_uid 參數（介面跟 memory.tsx 共用），這裡固定傳空字串——
// memory_route._resolve_conf_uid 對空字串一律視為「沒帶」而退回 base，不會
// 400、也不會誤寫到某個角色專屬設定（memory.tsx 檔頭的同一段說明也適用在
// 這裡）。
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
import { setMemoryConsolidation } from '@/api/memory.ts';

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

// 整理頻率選項目前固定是 {1,3,5}（memory_core.CONSOLIDATE_INTERVAL_CHOICES），
// 各自有專屬翻譯鍵。跟 presetNameKey 一樣，找不到對應鍵時直接顯示數字，不讓
// 未來後端多開一個新選項時整個下拉選單壞掉。
function consolidationLabelKey(n: number): string | null {
  if (n === 1) return 'settings.perf.consolidationEvery1';
  if (n === 3) return 'settings.perf.consolidationEvery3';
  if (n === 5) return 'settings.perf.consolidationEvery5';
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

  // 載入現值。refreshTick 讓套用 preset 成功後可以重新拉一次，三個區塊都要
  // 反映新寫入的值（preset 一次改了 asr/tts/keep_alive/consolidation 四個
  // 會出現在這個分頁上的欄位）。
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

  const consolidationCollection = useMemo(() => createListCollection({
    items: (perf?.consolidation_interval_choices ?? []).map((n) => {
      const key = consolidationLabelKey(n);
      return { label: key ? t(key) : String(n), value: String(n) };
    }),
  }), [perf?.consolidation_interval_choices, t]);

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

  const handleConsolidationChange = useCallback(async (value: string[]) => {
    const interval = Number(value[0]);
    // 先前這裡有一道 `if (!isValidConsolidation(interval)) return;`。它用的是
    // api/memory.ts 裡寫死的 {1,3,5}，而上面的下拉選單是用伺服器送來的
    // consolidation_interval_choices 建的——兩邊一旦不同步，使用者選得到卻存
    // 不了，而且是一個沒有任何提示的 return。setMemoryConsolidation 自己就會
    // 驗證並回傳可翻譯的錯誤鍵（它的註解特別為此設計），這道前置守衛只是讓那
    // 條路徑永遠到不了。拿掉，讓錯誤真的浮上來。
    const result = await setMemoryConsolidation(baseUrl, '', interval);
    if (result.ok) {
      setPerf((p) => (p ? { ...p, consolidation_interval: interval } : p));
      toaster.create({
        title: t('settings.perf.saved'),
        description: t('settings.perf.restartHint'),
        type: 'success',
        duration: 4000,
      });
    } else {
      toaster.create({
        // result.error 可能是 i18n 鍵（api 層刻意回傳穩定識別碼）或是網路層的
        // 人話訊息。用開頭判斷，別把後者也丟進 t()。
        title: result.error
          ? (result.error.startsWith('settings.') ? t(result.error) : result.error)
          : t('settings.perf.saveFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, t]);

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

      {/* 記憶整理頻率：下拉選單，選了就存——跟 memory.tsx 的開關類控制同一種
          即時存檔模式，不需要額外的儲存按鈕（選單本身就是離散、確定的動作，
          不像文字輸入框有「打到一半」的中間狀態）。呼叫的是 api/memory.ts 的
          setMemoryConsolidation，不是 perf 命名空間那支未使用的版本——見本檔
          檔頭與 api/perf.ts 檔尾的說明，兩個端點寫的是同一個設定葉，
          memory 命名空間才是這個 UI 實際呼叫的權威寫法。 */}
      <Stack gap={2}>
        <Heading size="sm">{t('settings.perf.consolidationSectionTitle')}</Heading>
        <SelectField
          label={t('settings.perf.consolidationLabel')}
          value={perf.consolidation_interval ? [String(perf.consolidation_interval)] : []}
          onChange={handleConsolidationChange}
          collection={consolidationCollection}
          placeholder={t('settings.perf.consolidationPlaceholder')}
        />
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.perf.consolidationHelp')}</Text>
      </Stack>
    </Stack>
  );
}

export default Perf;
