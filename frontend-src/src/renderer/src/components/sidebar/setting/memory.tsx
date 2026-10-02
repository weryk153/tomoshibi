// 記憶：她自己的記憶（角色層、所有對話共用）與這段對話的記憶。嵌在角色頁的
// 記憶區，confUid 由角色頁傳進來；只有正在用的角色才會顯示這一區——記憶屬於
// 一段對話，非使用中的角色沒有對話，後端會回 409。長期記憶的開關不在這裡：
// 它是角色檔的欄位，跟翻字幕、動作描寫一樣由角色頁的 saveCharacterSettings 寫。
import {
  useState, useEffect, useCallback, useRef,
} from 'react';
import {
  Stack, Text, Heading, HStack, Textarea, Collapsible, Box,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { HiChevronDown, HiChevronRight } from 'react-icons/hi';
import { settingStyles } from './setting-styles';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { useWebSocket } from '@/context/websocket-context';
import {
  fetchMemory,
  saveMemoryContent,
  clearMemory,
  saveSelfMemoryContent,
  clearSelfMemory,
  type MemoryState,
} from '@/api/memory.ts';

function Memory({ confUid }: { confUid: string }): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();

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

  // 她自己的記憶：角色層、所有對話共用。跟 contentDraft 同一套保護——POST 是整份
  // 取代，載入前不准存。
  const [selfDraft, setSelfDraft] = useState('');
  const [pendingClearSelf, setPendingClearSelf] = useState(false);
  const [clearingSelf, setClearingSelf] = useState(false);

  const [pendingClear, setPendingClear] = useState(false);
  const [clearing, setClearing] = useState(false);


  const [advancedOpen, setAdvancedOpen] = useState(false);

  // 載入現值。confUid 改變（切換角色）或 refreshTick 遞增（破壞性操作完成後
  // 想確認結果）都要重新拉一次，不用整頁重載。
  //
  // 同時在這裡重置「待確認」旗標（pendingClear／pendingClearSelf）。切換角色時
  // 這個元件不一定會 unmount（setting-ui.tsx 的分頁掛載過就留著），state 會
  // 整份留著。若使用者對角色 A 開了「清除記憶」的確認框，再切去
  // 別的分頁換成角色 B，回到這一區時如果沒有這行，紅色確認框仍會開著，
  // 但 confUid 已經指向 B：按下確認會呼叫 clearMemory(confUid=B)，不可逆地
  // 清掉「B」的核心記憶，而使用者以為自己在確認清掉 A。這不是防禦性多寫，是
  // 唯一的重置點——不要因為「看起來多餘」就把這段搬走或精簡掉，那會讓上述資料
  // 遺失路徑無聲地復活。
  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    setContentLoaded(false);
    setPendingClear(false);
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

  // 長文字：離開欄位才存（不在停頓時存，不然改到一半就把記憶整份換掉）。每一筆帶著
  // 它屬於哪個角色，排隊中換了角色也不會存到別人身上。
  const BLUR_ONLY_MS = 60 * 60 * 1000;
  // 存檔時才讀「現在存著的是哪一版」當起點（edited_from），不用排進去那一刻的：
  // 上一筆剛存好、這一筆才送的話，起點要是剛存好的那一版，刪掉的行才不會被加回來。
  const memoryRef = useRef(memory);
  memoryRef.current = memory;
  const selfDraftRef = useRef(selfDraft);
  selfDraftRef.current = selfDraft;
  // 起點只對同一個角色有意義：排隊中換了角色，就不帶起點（不拿別人的記憶當基準）。
  const uidRef = useRef(confUid);
  uidRef.current = confUid;
  const startingPoint = (uid: string, pick: (m: NonNullable<typeof memory>) => string): string | undefined => (
    uid === uidRef.current && memoryRef.current ? pick(memoryRef.current) : undefined
  );
  const contentSaver = useAutosave(async (edit: { uid: string; draft: string }) => {
    const from = startingPoint(edit.uid, (m) => m.content);
    const result = await saveMemoryContent(baseUrl, edit.uid, edit.draft, from);
    if (!result.ok) {
      return { ok: false, error: result.error || t('settings.memory.saveContentFailed') } as const;
    }
    memoryRef.current = memoryRef.current ? { ...memoryRef.current, content: edit.draft } : memoryRef.current;
    setMemory((m) => (m ? { ...m, content: edit.draft } : m));
    return { ok: true } as const;
  }, { delayMs: BLUR_ONLY_MS });

  const selfSaver = useAutosave(async (edit: { uid: string; draft: string }) => {
    const from = startingPoint(edit.uid, (m) => m.self_content);
    const result = await saveSelfMemoryContent(baseUrl, edit.uid, edit.draft, from);
    if (!result.ok) {
      return { ok: false, error: result.error || t('settings.memory.saveContentFailed') } as const;
    }
    // 引擎有上限，存進去的不一定全部留下：顯示它實際記得的那一份。不然下次
    // 存檔時，被擠掉的那幾行會被當成新的又加回去。
    const stored = typeof result.data?.content === 'string' ? result.data.content : edit.draft;
    memoryRef.current = memoryRef.current ? { ...memoryRef.current, self_content: stored } : memoryRef.current;
    // 存檔途中又打了字就不蓋掉，下一次存檔會帶著新的字送出去。
    if (selfDraftRef.current === edit.draft) setSelfDraft(stored);
    setMemory((m) => (m ? { ...m, self_content: stored } : m));
    return { ok: true } as const;
  }, { delayMs: BLUR_ONLY_MS });

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
                onChange={(e) => {
                  setSelfDraft(e.target.value);
                  selfSaver.change({ uid: confUid, draft: e.target.value });
                }}
                onBlur={selfSaver.flush}
                placeholder={t('settings.memory.empty')}
                disabled={!contentLoaded}
              />
              <Text fontSize="xs" color="whiteAlpha.600">
                {t('settings.memory.charCountNoCap', { count: selfDraft.length })}
              </Text>
              <SaveStatus state={selfSaver.state} />
              {!pendingClearSelf && (
                <HStack>
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
                onChange={(e) => {
                  setContentDraft(e.target.value);
                  contentSaver.change({ uid: confUid, draft: e.target.value });
                }}
                onBlur={contentSaver.flush}
                placeholder={t('settings.memory.empty')}
                disabled={!contentLoaded}
              />
              <Text fontSize="xs" color="whiteAlpha.600">
                {t('settings.memory.charCountNoCap', { count: contentDraft.length })}
              </Text>
              <Text fontSize="xs" color="whiteAlpha.500">{t('settings.memory.editHint')}</Text>
              <SaveStatus state={contentSaver.state} />
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
