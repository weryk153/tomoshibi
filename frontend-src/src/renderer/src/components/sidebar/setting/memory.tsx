/* eslint-disable import/no-extraneous-dependencies */
// memory 分頁：長期記憶管理。跟 Characters／LLM／About 一樣是無 props 的分頁
// （見 setting-ui.tsx 的三處註冊）——存檔是即時打 API，不需要外層抽屜的
// Save/Cancel 去觸發。
//
// 版面依 spec §4.3：核心在前（開關、核心記憶上限），進階收在展開區但完整保留
// （手動編輯核心記憶文字＋字數、深度回想開關與 top-k、重建索引）。第一版設計
// 提議移除進階控制，spec 記載那是閹割不是精簡，這裡原樣保留、只是收起來。
//
// conf_uid 用 useConfig().confUid（既有的 CharacterConfigContext），由
// websocket-handler 收到後端 'set-model-and-conf' 訊息時填入，代表「目前使用中
// 的角色」。memory_route.py 檔頭註解明講：「The frontend already tracks the
// active conf_uid (from the WS 'set-model-and-conf' message), so it passes it
// explicitly」——講的就是這個 context，所以直接沿用，不用另外做角色選單，也
// 不用猜一個 conf_uid。WS 訊息送達前 confUid 是空字串，這時後端
// _resolve_conf_uid 對空字串一律視為「沒帶」而退回 base 角色（見
// memory_route.py 的 `str(supplied).strip()` 判斷），所以空字串送出是安全的，
// 不會打到未知角色或觸發 400——切換角色時 confUid 改變，下面的 effect 會重新
// 載入。
import {
  useState, useEffect, useCallback,
} from 'react';
import {
  Stack, Text, Heading, HStack, Textarea, Collapsible, Box,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { HiChevronDown, HiChevronRight } from 'react-icons/hi';
import { settingStyles } from './setting-styles';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import { SwitchField, NumberField } from './common';
import {
  fetchMemory,
  saveMemoryContent,
  setMemoryEnabled,
  setMemoryCap,
  clearMemory,
  clampCap,
  type MemoryState,
} from '@/api/memory.ts';

// 見 src/open_llm_vtuber/memory_core.py 的 CAP_MIN／CAP_MAX 與 memory_route.py
// memory.ts 沒有把 cap 邊界匯出成常數——clampCap
// 內部就會夾住，呼叫端本來就不需要知道邊界值才能送出合法請求——但
// NumberField 的 min/max 需要實際數字才能限制輸入框與提示文字，所以在這裡重複
// 一份，來源與 memory.ts 開頭引用的後端檔案一致。
// 這四個是 fallback：memory 還沒載入完成時畫面仍要有可用的範圍。載入之後
// 一律改用伺服器送來的 cap_min／cap_max
// （見 api/memory.ts 的說明）——伺服器才是界限的權威。
const CAP_MIN = 500;
const CAP_MAX = 8000;

interface MemoryProps {
  // 這個分頁目前是不是使用者看得到的那個 tab（setting-ui.tsx 依 activeTab
  // 算出）。用來在套用 perf 的一鍵模式後，使用者切回這個分頁時重新拉一次
  // core_memory_max_chars 這個 preset 會寫的欄位——見下面
  // 那個獨立的 fetchMemory effect 旁的說明。預設 true：萬一哪天有別的呼叫端
  // 沒傳這個 prop（目前只有 setting-ui.tsx 一處註冊），行為退回「一律當作
  // 可見」。
  active?: boolean
}

function Memory({ active = true }: MemoryProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { confUid } = useConfig();

  const [memory, setMemory] = useState<MemoryState | null>(null);

  // 界限一律以伺服器為準，載入前才用上面的 fallback。
  const capMin = memory?.cap_min ?? CAP_MIN;
  const capMax = memory?.cap_max ?? CAP_MAX;
  const [loadError, setLoadError] = useState<string | null>(null);
  // refreshTick 的遞增端（重建索引）已隨深度回憶一起移除；讀取端與機制
  // 保留，之後的破壞性操作要重抓現值時直接 setRefreshTick 即可。
  const [refreshTick, _setRefreshTick] = useState(0);

  // 手動編輯核心記憶文字。POST /api/memory 是整份取代，所以 contentLoaded 在
  // 現值真正載入完成前一律是 false，textarea 與存檔按鈕都保持停用——避免對著
  // 空白或半載入的表單按下存檔，把使用者的記憶整份清空。
  const [contentDraft, setContentDraft] = useState('');
  const [contentLoaded, setContentLoaded] = useState(false);
  const [savingContent, setSavingContent] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [pendingSaveContent, setPendingSaveContent] = useState(false);

  const [capDraft, setCapDraft] = useState('');
  const [savingCap, setSavingCap] = useState(false);


  const [pendingClear, setPendingClear] = useState(false);
  const [clearing, setClearing] = useState(false);


  const [advancedOpen, setAdvancedOpen] = useState(false);

  // 載入現值。confUid 改變（切換角色）或 refreshTick 遞增（破壞性操作完成後
  // 想確認結果）都要重新拉一次，不用整頁重載。
  //
  // 同時在這裡重置三個「待確認」旗標（pendingSaveContent／pendingClear／
  // ）。Memory 分頁在切換角色時不會 unmount——setting-ui.tsx 的
  // Tabs.Root 沒設 lazyMount／unmountOnExit，General 分頁切換角色是直接打
  // WebSocket（見 use-general-settings.ts），不會重新掛載這個元件——state 會
  // 整份留著。若使用者對角色 A 開了「清除記憶」或「重建索引」的確認框，再切去
  // 別的分頁換成角色 B，回到 Memory 分頁時如果沒有這行，紅色確認框仍會開著，
  // 但 confUid 已經指向 B：按下確認會呼叫 clearMemory(confUid=B)，不可逆地
  // 清掉「B」的核心記憶，而使用者以為自己在確認清掉 A。這不是防禦性多寫，是
  // 唯一的重置點——不要因為「看起來多餘」就把這段搬走或精簡掉，那會讓上述資料
  // 遺失路徑無聲地復活。
  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    setContentLoaded(false);
    setPendingSaveContent(false);
    setPendingClear(false);
    (async () => {
      const result = await fetchMemory(baseUrl, confUid);
      if (cancelled) return;
      if (result.ok) {
        setMemory(result.data);
        setContentDraft(result.data.content);
        setContentLoaded(true);
        setCapDraft(String(result.data.cap));
      } else {
        setLoadError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl, confUid, refreshTick]);

  // 套用 perf 分頁的一鍵模式會原子寫入 core_memory_max_chars
  // 兩個這個分頁也在顯示的欄位（見 perf_route.PRESETS）。這個分頁如果早就掛載
  // 著（Tabs.Content 預設不做 lazyMount，抽屜一打開就都掛了），畫面停在套用前
  // 抓到的那份不會自動更新——跟 asr.tsx／tts.tsx 同一個破綻、同一份任務簡報
  // Fix 1，只是這裡多一個地雷：下面存 cap 的按鈕（handleCapSave）送出的是
  // capDraft 目前顯示的值，不是「有沒有改過」的差異——如果 capDraft 沒跟著更新
  // 就停在套用前的舊值，使用者之後隨手按一次「儲存」（哪怕只是想存別的東西時
  // 順手按到），就會把剛套用的 preset 值悄悄改回舊的，這是任務簡報點名的第二
  // 種後果，不只是顯示不對。
  //
  // 這個 effect 故意不把 confUid 放進依賴陣列（用 closure 讀目前值就好，跟下面
  // handleToggle 等 callback 讀 confUid 的方式一致）：confUid 改變（切換角色）
  // 已經由上面那個 effect 完整處理（它的依賴陣列本來就有 confUid，會整份重新
  // 載入，capDraft 也在裡面），這裡如果重複依賴 confUid，角色切換時會跟主要
  // effect 的 fetchMemory 同時打出兩個請求，晚回來的那個可能用「切換前那個
  // 角色」的 memory 狀態去比較 capDraft 有沒有異動，把不相干的一次判斷結果套
  // 用到新角色身上。這裡只處理「同一個角色、分頁重新變成可見」這一種情境。
  //
  // 修法：切回這個分頁時只重新拉這兩個欄位，不叫 fetchMemory 整份重新載入——
  // 特意不重用上面那個 effect／不去動 refreshTick，因為那個 effect 一啟動就會
  // setContentDraft(result.data.content) 整份覆寫核心記憶文字框、並重置
  // pendingSaveContent／pendingClear 兩個確認旗標。核心記憶的
  // 存檔是整份取代（見檔頭與 handleContentSave 旁的說明），使用者這時可能正在
  // textarea 裡打一段還沒存的手動編輯——切分頁再切回來就把打到一半的文字換成
  // 伺服器的舊內容，是比這次要修的顯示錯誤更糟的資料遺失，絕對不能做。
  //
  // cap 有草稿（capDraft），用「目前草稿是否還等於上一次載入的伺服器值」判斷
  // 有沒有在編輯中——沒異動就跟著刷新，有異動（使用者正在打字，還沒按下面的
  // 儲存）就不覆寫，把使用者半打的數字保留下來。
  //
  // 讀取失敗時不設 loadError：這只是背景刷新，失敗了維持原本已經在畫面上、能
  // 動作的那份資料。
  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    (async () => {
      const result = await fetchMemory(baseUrl, confUid);
      if (cancelled || !result.ok) return;
      const data = result.data;
      setCapDraft((prev) => (
        memory && prev !== String(memory.cap) ? prev : String(data.cap)
      ));
      setMemory((m) => (m ? { ...m, cap: data.cap } : m));
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, baseUrl]);

  const handleToggle = useCallback(async (checked: boolean) => {
    const result = await setMemoryEnabled(baseUrl, confUid, checked);
    if (result.ok) {
      setMemory((m) => (m ? { ...m, enabled: checked } : m));
      toaster.create({
        title: t('settings.memory.saved'),
        description: t('settings.memory.restartHintSetting'),
        type: 'success',
        duration: 5000,
      });
    } else {
      toaster.create({
        title: result.error || t('settings.memory.saveFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, confUid, t]);

  // 兩個 clampCap 陷阱都要在這裡擋下：
  // 1) NumberField 給的 value 是字串，clampCap 不會做字串轉數字（"6000" 會被
  //    Number.isFinite 判定為非數字而夾到下界 500），所以先用 Number() 轉成
  //    數字再交給 clampCap。
  // 2) clampCap 只保證落在 [CAP_MIN, CAP_MAX] 之內，不保證是整數——750.5 會
  //    原封不動通過，後端 int() 會悄悄把它截斷成 750。這裡用 Math.round 在
  //    送出前抹平小數，不是只靠 <input step>：settingStyles 裡
  //    numberInput.root 的 pattern 是 `[0-9]*\.?[0-9]*`，容許輸入小數點，
  //    使用者用鍵盤打字仍能繞過 step 限制，唯一可靠的地方是送出前。
  const handleCapSave = useCallback(async () => {
    const clamped = Math.round(clampCap(Number(capDraft)));
    setSavingCap(true);
    const result = await setMemoryCap(baseUrl, confUid, clamped);
    setSavingCap(false);
    if (result.ok) {
      setMemory((m) => (m ? { ...m, cap: clamped } : m));
      setCapDraft(String(clamped));
      toaster.create({
        title: t('settings.memory.capSaved'),
        description: t('settings.memory.restartHintSetting'),
        type: 'success',
        duration: 5000,
      });
    } else {
      toaster.create({
        title: result.error || t('settings.memory.saveFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, confUid, capDraft, t]);

  // 破壞性操作 1／3：POST /api/memory 是整份取代，不是合併。contentLoaded 已
  // 在 UI 層擋住「現值還沒載入完成就存檔」，這裡再擋一次做為最後防線。真正的
  // 確認步驟是 pendingSaveContent：按第一次「儲存記憶」只會顯示確認區塊，要再
  // 按一次才會真的送出。
  const handleContentSave = useCallback(async () => {
    if (!contentLoaded) return;
    setSavingContent(true);
    setSaveError(null);
    const result = await saveMemoryContent(baseUrl, confUid, contentDraft);
    setSavingContent(false);
    setPendingSaveContent(false);
    if (result.ok) {
      setMemory((m) => (m
        ? { ...m, content: contentDraft, char_count: contentDraft.length }
        : m));
      toaster.create({
        title: t('settings.memory.saved'),
        description: t('settings.memory.restartHint'),
        type: 'success',
        duration: 4000,
      });
    } else {
      setSaveError(result.error || t('settings.memory.saveContentFailed'));
    }
  }, [baseUrl, confUid, contentDraft, contentLoaded, t]);

  // 破壞性操作 2／3：POST /api/memory/clear。pendingClear 就是確認步驟——先顯示
  // 確認區塊，使用者再按一次紅色按鈕才真的清空。
  const handleClear = useCallback(async () => {
    setClearing(true);
    const result = await clearMemory(baseUrl, confUid);
    setClearing(false);
    setPendingClear(false);
    if (result.ok) {
      setContentDraft('');
      setMemory((m) => (m ? { ...m, content: '', char_count: 0 } : m));
      toaster.create({ title: t('settings.memory.cleared'), type: 'success', duration: 2500 });
    } else {
      toaster.create({
        title: result.error || t('settings.memory.clearFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, confUid, t]);


  if (loadError) {
    return (
      <Stack {...settingStyles.common.container}>
        <Text fontSize="sm" color="red.300">{loadError}</Text>
      </Stack>
    );
  }

  if (!memory) {
    return (
      <Stack {...settingStyles.common.container}>
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.memory.loading')}</Text>
      </Stack>
    );
  }

  return (
    <Stack {...settingStyles.common.container} maxW="none">
      <Text fontSize="sm" color="whiteAlpha.700">{t('settings.memory.description')}</Text>

      {/* 核心：開關＋核心記憶上限，spec 要求打開分頁第一眼就看到 */}
      <SwitchField
        label={t('settings.memory.toggle')}
        checked={memory.enabled}
        onChange={handleToggle}
        help={t('settings.memory.toggleHelp')}
      />

      <Stack gap={2}>
        <NumberField
          label={t('settings.memory.capLabel', { min: capMin, max: capMax })}
          value={capDraft}
          onChange={setCapDraft}
          min={capMin}
          max={capMax}
          step={1}
          help={t('settings.memory.capHelp', { min: CAP_MIN, max: CAP_MAX })}
        />
        <HStack>
          <Button size="xs" tone="blue" onClick={handleCapSave} loading={savingCap}>
            {t('common.save')}
          </Button>
        </HStack>
      </Stack>

      {/* 進階：收在展開區，但功能齊全——手動編輯記憶、深度回想、重建索引都在
          這裡，不是被移除，只是不該是打開分頁第一眼看到的東西。 */}
      <Collapsible.Root
        open={advancedOpen}
        onOpenChange={(details) => setAdvancedOpen(details.open)}
      >
        <Collapsible.Trigger asChild>
          <Button size="xs" variant="ghost">
            {advancedOpen ? <HiChevronDown /> : <HiChevronRight />}
            {t('settings.memory.advancedToggle')}
          </Button>
        </Collapsible.Trigger>
        <Collapsible.Content>
          <Stack gap={6} mt={4}>
            {/* 手動編輯核心記憶 */}
            <Stack gap={2}>
              <Heading size="sm">{t('settings.memory.viewLabel')}</Heading>
              <Textarea
                rows={8}
                value={contentDraft}
                onChange={(e) => setContentDraft(e.target.value)}
                placeholder={t('settings.memory.empty')}
                disabled={!contentLoaded}
              />
              <Text fontSize="xs" color="whiteAlpha.600">
                {t('settings.memory.charCount', { count: contentDraft.length, cap: memory.cap })}
              </Text>
              <Text fontSize="xs" color="whiteAlpha.500">{t('settings.memory.editHint')}</Text>
              {saveError && (
                <Text fontSize="xs" color="red.300">{saveError}</Text>
              )}
              {!pendingSaveContent ? (
                <HStack>
                  <Button
                    size="xs"
                    tone="blue"
                    disabled={!contentLoaded}
                    onClick={() => setPendingSaveContent(true)}
                  >
                    {t('settings.memory.save')}
                  </Button>
                </HStack>
              ) : (
                <Box p={2} borderWidth="1px" borderColor="orange.700" borderRadius="sm">
                  <Text fontSize="xs">{t('settings.memory.saveConfirm')}</Text>
                  <HStack mt={2}>
                    <Button
                      size="xs"
                      tone="blue"
                      onClick={handleContentSave}
                      loading={savingContent}
                    >
                      {t('settings.characters.confirm')}
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => setPendingSaveContent(false)}
                      disabled={savingContent}
                    >
                      {t('common.cancel')}
                    </Button>
                  </HStack>
                </Box>
              )}
            </Stack>

            {/* 清除記憶 */}
            <Stack gap={2}>
              {!pendingClear ? (
                <HStack>
                  <Button
                    size="xs"
                    tone="red"
                    variant="outline"
                    onClick={() => setPendingClear(true)}
                  >
                    {t('settings.memory.clear')}
                  </Button>
                </HStack>
              ) : (
                <Box p={2} borderWidth="1px" borderColor="red.700" borderRadius="sm">
                  <Text fontSize="xs">{t('settings.memory.clearConfirm')}</Text>
                  <HStack mt={2}>
                    <Button
                      size="xs"
                      tone="red"
                      onClick={handleClear}
                      loading={clearing}
                    >
                      {t('settings.characters.confirm')}
                    </Button>
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => setPendingClear(false)}
                      disabled={clearing}
                    >
                      {t('common.cancel')}
                    </Button>
                  </HStack>
                </Box>
              )}
            </Stack>
          </Stack>
        </Collapsible.Content>
      </Collapsible.Root>
    </Stack>
  );
}

export default Memory;
