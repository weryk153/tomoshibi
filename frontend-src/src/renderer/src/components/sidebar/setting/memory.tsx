// memory 分頁：長期記憶管理。跟 Characters／LLM／About 一樣是無 props 的分頁
// （見 setting-ui.tsx 的三處註冊）——存檔是即時打 API，不需要外層抽屜的
// Save/Cancel 去觸發。
//
// 記憶全在引擎手上：核心是開關，手動編輯她自己的記憶與這段對話的記憶收在
// 展開區。
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
import { SwitchField } from './common';
import {
  fetchMemory,
  saveMemoryContent,
  setMemoryEnabled,
  clearMemory,
  saveSelfMemoryContent,
  clearSelfMemory,
  type MemoryState,
} from '@/api/memory.ts';

function Memory(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { confUid } = useConfig();

  const [memory, setMemory] = useState<MemoryState | null>(null);

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

  // 她自己的記憶：角色層、所有對話共用。跟 contentDraft 同一套保護——POST 是整份
  // 取代，載入前不准存。
  const [selfDraft, setSelfDraft] = useState('');
  const [savingSelf, setSavingSelf] = useState(false);
  const [saveSelfError, setSaveSelfError] = useState<string | null>(null);
  const [pendingSaveSelf, setPendingSaveSelf] = useState(false);
  const [pendingClearSelf, setPendingClearSelf] = useState(false);
  const [clearingSelf, setClearingSelf] = useState(false);

  const [pendingClear, setPendingClear] = useState(false);
  const [clearing, setClearing] = useState(false);


  const [advancedOpen, setAdvancedOpen] = useState(false);

  // 載入現值。confUid 改變（切換角色）或 refreshTick 遞增（破壞性操作完成後
  // 想確認結果）都要重新拉一次，不用整頁重載。
  //
  // 同時在這裡重置「待確認」旗標（pendingSaveContent／pendingClear／
  // pendingSaveSelf／pendingClearSelf）。Memory 分頁在切換角色時不會 unmount——setting-ui.tsx 的
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
    setPendingSaveSelf(false);
    setPendingClearSelf(false);
    (async () => {
      const result = await fetchMemory(baseUrl, confUid);
      if (cancelled) return;
      if (result.ok) {
        setMemory(result.data);
        setContentDraft(result.data.content);
        setSelfDraft(result.data.self_content);
        setContentLoaded(true);
      } else {
        setLoadError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl, confUid, refreshTick]);

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

  // 破壞性操作 1／3：POST /api/memory 是整份取代，不是合併。contentLoaded 已
  // 在 UI 層擋住「現值還沒載入完成就存檔」，這裡再擋一次做為最後防線。真正的
  // 確認步驟是 pendingSaveContent：按第一次「儲存記憶」只會顯示確認區塊，要再
  // 按一次才會真的送出。
  const handleContentSave = useCallback(async () => {
    if (!contentLoaded) return;
    setSavingContent(true);
    setSaveError(null);
    // memory.content 是這次編輯的起點：載入時放進 textarea 的那一版，存檔成功後
    // 換成剛存的，所以它跟 textarea 一致。
    const result = await saveMemoryContent(
      baseUrl, confUid, contentDraft, memory?.content,
    );
    setSavingContent(false);
    setPendingSaveContent(false);
    if (result.ok) {
      setMemory((m) => (m ? { ...m, content: contentDraft } : m));
      toaster.create({
        title: t('settings.memory.saved'),
        description: t('settings.memory.restartHint'),
        type: 'success',
        duration: 4000,
      });
    } else {
      setSaveError(result.error || t('settings.memory.saveContentFailed'));
    }
  }, [baseUrl, confUid, contentDraft, contentLoaded, memory?.content, t]);

  // 破壞性操作 2／3：POST /api/memory/clear。pendingClear 就是確認步驟——先顯示
  // 確認區塊，使用者再按一次紅色按鈕才真的清空。
  const handleClear = useCallback(async () => {
    setClearing(true);
    const result = await clearMemory(baseUrl, confUid);
    setClearing(false);
    setPendingClear(false);
    if (result.ok) {
      setContentDraft('');
      setMemory((m) => (m ? { ...m, content: '' } : m));
      toaster.create({ title: t('settings.memory.cleared'), type: 'success', duration: 2500 });
    } else {
      toaster.create({
        title: result.error || t('settings.memory.clearFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, confUid, t]);

  const handleSelfSave = useCallback(async () => {
    if (!contentLoaded) return;
    setSavingSelf(true);
    setSaveSelfError(null);
    const result = await saveSelfMemoryContent(
      baseUrl, confUid, selfDraft, memory?.self_content,
    );
    setSavingSelf(false);
    setPendingSaveSelf(false);
    if (result.ok) {
      // 引擎有上限，存進去的不一定全部留下：顯示它實際記得的那一份。不然下次
      // 存檔時，被擠掉的那幾行會被當成新的又加回去。
      const stored = typeof result.data?.content === 'string' ? result.data.content : selfDraft;
      setSelfDraft(stored);
      setMemory((m) => (m ? { ...m, self_content: stored } : m));
      toaster.create({
        title: t('settings.memory.saved'),
        description: t('settings.memory.restartHint'),
        type: 'success',
        duration: 4000,
      });
    } else {
      setSaveSelfError(result.error || t('settings.memory.saveContentFailed'));
    }
  }, [baseUrl, confUid, selfDraft, contentLoaded, memory?.self_content, t]);

  const handleSelfClear = useCallback(async () => {
    setClearingSelf(true);
    const result = await clearSelfMemory(baseUrl, confUid);
    setClearingSelf(false);
    setPendingClearSelf(false);
    if (result.ok) {
      setSelfDraft('');
      setMemory((m) => (m ? { ...m, self_content: '' } : m));
      toaster.create({ title: t('settings.memory.selfCleared'), type: 'success', duration: 2500 });
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

      {/* 核心：開關，打開分頁第一眼就看到 */}
      <SwitchField
        label={t('settings.memory.toggle')}
        checked={memory.enabled}
        onChange={handleToggle}
        help={t('settings.memory.toggleHelp')}
      />

      {/* 進階：收在展開區——手動編輯她自己的記憶與這段對話的記憶，不該是打開
          分頁第一眼看到的東西。 */}
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
            {/* 她自己的記憶：角色層、所有對話共用，排在前面 */}
            <Stack gap={2}>
              <Heading size="sm">{t('settings.memory.selfLabel')}</Heading>
              <Text fontSize="xs" color="whiteAlpha.600">{t('settings.memory.selfHelp')}</Text>
              <Textarea
                rows={5}
                value={selfDraft}
                onChange={(e) => setSelfDraft(e.target.value)}
                placeholder={t('settings.memory.empty')}
                disabled={!contentLoaded}
              />
              <Text fontSize="xs" color="whiteAlpha.600">
                {t('settings.memory.charCountNoCap', { count: selfDraft.length })}
              </Text>
              {saveSelfError && (
                <Text fontSize="xs" color="red.300">{saveSelfError}</Text>
              )}
              {!pendingSaveSelf ? (
                <HStack>
                  <Button size="xs" tone="blue" disabled={!contentLoaded} onClick={() => setPendingSaveSelf(true)}>
                    {t('settings.memory.selfSave')}
                  </Button>
                  {/* contentLoaded 同時是「畫面上這份內容真的屬於現在這個
                      confUid」的旗標。切換角色時上面那個 effect 先把它設回
                      false，重抓完成才設回 true——中間這段時間畫面還是 A 的
                      內容、confUid 已經是 B，清除鍵按兩下就把 B 清掉了，而
                      使用者以為自己在清 A。存檔鍵已經擋了，清除鍵一樣要擋。 */}
                  <Button
                    size="xs"
                    tone="red"
                    variant="outline"
                    disabled={!contentLoaded}
                    onClick={() => setPendingClearSelf(true)}
                  >
                    {t('settings.memory.selfClear')}
                  </Button>
                </HStack>
              ) : (
                <Box p={2} borderWidth="1px" borderColor="orange.700" borderRadius="sm">
                  <Text fontSize="xs">{t('settings.memory.selfSaveConfirm')}</Text>
                  <HStack mt={2}>
                    <Button size="xs" tone="blue" onClick={handleSelfSave} loading={savingSelf}>
                      {t('settings.characters.confirm')}
                    </Button>
                    <Button size="xs" variant="ghost" onClick={() => setPendingSaveSelf(false)} disabled={savingSelf}>
                      {t('common.cancel')}
                    </Button>
                  </HStack>
                </Box>
              )}
              {pendingClearSelf && (
                <Box p={2} borderWidth="1px" borderColor="red.700" borderRadius="sm">
                  <Text fontSize="xs">{t('settings.memory.selfClearConfirm')}</Text>
                  <HStack mt={2}>
                    <Button size="xs" tone="red" onClick={handleSelfClear} loading={clearingSelf}>
                      {t('settings.characters.confirm')}
                    </Button>
                    <Button size="xs" variant="ghost" onClick={() => setPendingClearSelf(false)} disabled={clearingSelf}>
                      {t('common.cancel')}
                    </Button>
                  </HStack>
                </Box>
              )}
            </Stack>

            {/* 這段對話的記憶 */}
            <Stack gap={2}>
              <Heading size="sm">{t('settings.memory.conversationLabel')}</Heading>
              <Text fontSize="xs" color="whiteAlpha.600">{t('settings.memory.conversationHelp')}</Text>
              <Textarea
                rows={8}
                value={contentDraft}
                onChange={(e) => setContentDraft(e.target.value)}
                placeholder={t('settings.memory.empty')}
                disabled={!contentLoaded}
              />
              <Text fontSize="xs" color="whiteAlpha.600">
                {t('settings.memory.charCountNoCap', { count: contentDraft.length })}
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
                  {/* 同上：載入完成前不准清除，避免清到剛切過去的那個角色。 */}
                  <Button
                    size="xs"
                    tone="red"
                    variant="outline"
                    disabled={!contentLoaded}
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
