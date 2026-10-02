// 「關於你」區塊：你的暱稱／頭像（純 localStorage，Step 1）、玩家語言與全域
// 指示（寫 conf.yaml，經 api/player.ts，Step 2／3）、目前角色的發聲語言
// （唯讀，衍生自 GET /api/characters 的 voice 欄位，Step 4）、用其他語言發聲＋
// 字幕翻譯（寫 conf.yaml，經 api/translator-config.ts，Step 5）。抽成獨立檔案的
// 理由見 general.tsx 內嵌處的註解：這幾組設定自成一個主題（「關於你」而不是
// 「關於 app」），general.tsx 加完 Task 3 的即時存檔區塊後已經接近可審查上限。
//
// 這裡每一項都改了就存：暱稱／頭像寫 localStorage，玩家語言、全域指示、翻譯
// 設定打 API（文字等停手或離開欄位才存）。寫進 conf.yaml 的要重新載入才生效，
// 由設定抽屜頂端的「還沒生效」提示統一處理，這裡不再各自跳「重啟後生效」。
//
// Step 5 刻意放在 Step 4（角色發聲語言，唯讀）之後：翻譯功能的 autoHint
// 講「發聲語言由角色的聲音決定」，講的正是 Step 4 顯示的那個值——這裡不重複
// 放一個「發聲語言」選單（那會變成第二個真相來源，見 service_context.py
// 對 voice_lang 的說明），只讓文案用「上面顯示的角色發聲語言」互相呼應。
// 同理，字幕的「進階：字幕用不同語言」提示會提到「上方的閱讀語言」，指的
// 就是 Step 2 的玩家語言選單——兩者在同一個元件裡，順序在它之後，這句話
// 才有着落。
import {
  useState, useEffect, useCallback, useRef, useMemo,
} from 'react';
import { Stack, Text, Heading, HStack, Box, Textarea } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useTranslation } from 'react-i18next';
import { settingStyles } from './setting-styles';
import { Button } from '@/components/ui/tw/primitives';
import { Field } from '@/components/ui/tw/primitives';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { SelectField, InputField } from './common';
import {
  fetchPlayerLanguage,
  setPlayerLanguage,
  fetchPlayerPrompt,
  setPlayerPrompt,
  PLAYER_LANGUAGES,
  playerLanguageValues,
} from '@/api/player.ts';
import {
  fetchCharacters, AVATAR_MAX_CLIENT_BYTES, type CharacterRecord,
} from '@/api/characters.ts';
import type { TranslatorEngine, TranslatorTestResult } from '@/api/translator-config.ts';
import { testTranslator } from '@/api/translator-config.ts';
import { useTranslatorSettings } from '@/hooks/sidebar/setting/use-translator-settings.ts';

// chat-history-panel.tsx 現在會讀這兩個 localStorage 鍵（userName 取
// displayName || 'Me'，頭像走跟 AI 那側同一種 img+onError fallback）。鍵名跟
// websocket-context.tsx 的 'wsUrl'／'baseUrl'、first-run-wizard.tsx 的
// 'setupWizardSkipped' 同一種扁平 camelCase 慣例，不加點號命名空間。
//
// useLocalStorage 只更新自己這個 component instance 的 state 並寫
// localStorage，不會通知其他 component（不是 pub/sub）；瀏覽器原生的
// 'storage' 事件本來就只在「別的分頁/視窗」改了同一個 key 時才會觸發，同一個
// document 內 setItem 不會自己收到。這個 app 是單一視窗的 Electron renderer，
// 不會有真的跨分頁情境，所以借用同一個事件型別、手動 dispatch 一份，讓
// chat-history-panel.tsx 用普通的 window.addEventListener('storage', ...) 就能
// 收到「同一份文件內」的變更，不用另外設計一套自訂事件、也不用改動
// use-local-storage.ts（它還有 vad-context.tsx／bgurl-context.tsx 等七個其他
// 呼叫端，不想動共用邏輯去換一個沒人在乎的功能）。
const USER_DISPLAY_NAME_KEY = 'userDisplayName';
const USER_AVATAR_KEY = 'userAvatarDataUrl';

function notifyLocalStorageChange(key: string, newValue: string): void {
  window.dispatchEvent(new StorageEvent('storage', { key, newValue }));
}

interface YouProps {
  // General 本身沒有從 setting-ui.tsx 拿到「目前是不是使用者看得到的分頁」
  // 這個訊號（不像 asr.tsx／memory.tsx 那樣接了 active prop），所以這個元件的
  // 三個 GET 在掛載時只會跑一次；active 保留給日後 general.tsx 也接上 activeTab
  // 訊號時可以直接派上用場，不用改這裡的邏輯。預設 true，理由同 memory.tsx 的
  // 同名 prop：目前唯一呼叫端（general.tsx）不傳時要退回「一律當作可見」。
  active?: boolean
}

function You({ active = true }: YouProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { confUid } = useConfig();

  // ---- Step 1：暱稱與頭像（純 localStorage）----
  const [displayName, setDisplayName] = useLocalStorage<string>(USER_DISPLAY_NAME_KEY, '');
  const [avatarDataUrl, setAvatarDataUrl] = useLocalStorage<string>(USER_AVATAR_KEY, '');
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const avatarInputRef = useRef<HTMLInputElement | null>(null);

  // 三條路徑分開判斷、分開回報，不合併成一個泛用錯誤：型別不符
  // （avatarNotImage）、超過大小（avatarTooLarge）、FileReader 失敗
  // （avatarReadFailed）在使用者眼中是三種不同的「怎麼辦」。大小上限沿用
  // characters.tsx／api/characters.ts 裡既有的 AVATAR_MAX_CLIENT_BYTES
  // （512KB），不另訂新常數。
  const handleAvatarFile = useCallback((file: File) => {
    setAvatarError(null);
    if (!file.type.startsWith('image/')) {
      setAvatarError(t('settings.user.avatarNotImage'));
      return;
    }
    if (file.size > AVATAR_MAX_CLIENT_BYTES) {
      setAvatarError(t('settings.user.avatarTooLarge'));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setAvatarDataUrl(reader.result);
        notifyLocalStorageChange(USER_AVATAR_KEY, reader.result);
      } else {
        setAvatarError(t('settings.user.avatarReadFailed'));
      }
    };
    reader.onerror = () => {
      setAvatarError(t('settings.user.avatarReadFailed'));
    };
    reader.readAsDataURL(file);
  }, [setAvatarDataUrl, t]);

  // ---- Step 2：玩家語言（寫 conf.yaml，經 setPlayerLanguage）----
  const [playerLang, setPlayerLangState] = useState('');
  const languageCollection = useMemo(() => createListCollection({
    items: playerLanguageValues(playerLang).map((value) => {
      const known = PLAYER_LANGUAGES.find((opt) => opt.value === value);
      return { label: known ? t(known.labelKey) : value, value };
    }),
  }), [playerLang, t]);
  const [languageLoadError, setLanguageLoadError] = useState<string | null>(null);
  // 後端最後一次確認存下的值；存失敗時退回它。
  const savedLangRef = useRef('');

  // 翻譯連線測試。結果留在畫面上直到下次測試，不用 toast——使用者需要一邊看著
  // 結果一邊調整上面的設定，會自己消失的提示在這裡幫不上忙。
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TranslatorTestResult | null>(null);
  const handleTestTranslator = useCallback(async () => {
    setTesting(true);
    setTestResult(null);
    const result = await testTranslator(baseUrl);
    setTesting(false);
    setTestResult(
      result.ok
        ? result.data
        // 連請求本身都失敗（伺服器沒回應／500）——歸到 error，訊息照實顯示。
        : { ok: false, reason: 'error', error: result.error },
    );
  }, [baseUrl]);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    setLanguageLoadError(null);
    (async () => {
      const result = await fetchPlayerLanguage(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setPlayerLangState(result.data);
        savedLangRef.current = result.data;
      } else {
        setLanguageLoadError(result.error || t('settings.playerLanguage.loadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl, active, t]);

  // 選了就存；失敗退回原值，不留一個「畫面上選了、conf.yaml 其實沒存到」的假象。
  const languageSaver = useAutosave(async (next: string) => {
    const result = await setPlayerLanguage(baseUrl, next);
    if (result.ok) {
      setPlayerLangState(result.data.language);
      savedLangRef.current = result.data.language;
      return { ok: true } as const;
    }
    setPlayerLangState(savedLangRef.current);
    return { ok: false, error: result.error || t('settings.playerLanguage.saveFailed') } as const;
  }, { delayMs: 0 });

  const handleLanguageChange = useCallback((value: string[]) => {
    const next = value[0] ?? '';
    setPlayerLangState(next);
    languageSaver.change(next);
  }, [languageSaver]);

  // ---- Step 3：全域指示（playerPrompt）----
  // 草稿式：改了不會自動送出，要按 save。送出前 setPlayerPrompt 內部已經先過
  // normalizePlayerPrompt，這裡不重複呼叫；送出成功後把 textarea 換成後端
  // 實際存下的字串（result.data.prompt），讓畫面跟 conf.yaml 一致——否則使用者
  // 打的三行字看起來還在，下次重開才發現只存了一行，像是資料被吃掉。
  const [promptDraft, setPromptDraft] = useState('');
  const [promptLoaded, setPromptLoaded] = useState(false);
  const [promptLoadError, setPromptLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    setPromptLoadError(null);
    (async () => {
      const result = await fetchPlayerPrompt(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setPromptDraft(result.data);
        setPromptLoaded(true);
      } else {
        setPromptLoadError(result.error || t('settings.playerPrompt.loadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl, active, t]);

  // 停手或離開欄位才存。存好後把欄位換成後端實際存下的字串（換行會被壓成一行）
  // ——但只在使用者送出之後沒再改的情況下，不蓋掉正在打的字。
  const promptDraftRef = useRef(promptDraft);
  promptDraftRef.current = promptDraft;
  const promptSaver = useAutosave(async (draft: string) => {
    const result = await setPlayerPrompt(baseUrl, draft);
    if (!result.ok) {
      return { ok: false, error: result.error || t('settings.playerPrompt.saveFailed') } as const;
    }
    if (promptDraftRef.current === draft) setPromptDraft(result.data.prompt);
    return { ok: true } as const;
  });

  // ---- Step 4：角色發聲語言（唯讀）----
  // 沿用 characters.tsx 同一個端點（GET /api/characters，api/characters.ts 的
  // fetchCharacters），不新增端點呼叫；只取目前角色（confUid 對應那筆）的
  // voice 欄位。edge-tts 的 ShortName 形如 zh-TW-HsiaoChenNeural，語言是前兩段。
  const [characters, setCharacters] = useState<CharacterRecord[] | null>(null);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    (async () => {
      const result = await fetchCharacters(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setCharacters(result.data.characters);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl, active]);

  // characters === null 涵蓋兩種狀況：GET 還沒回來（pending），或回來失敗
  // （fetchCharacters 失敗時 result.ok 是 false，上面的 effect 不會呼叫
  // setCharacters，characters 永遠停在 null）。這兩種狀況都回傳 null，讓下面
  // render 端整段不畫——後端掛掉時，不能讓使用者看到一句聽起來很篤定、其實
  // 沒查到任何東西的「角色發聲語言」宣稱。
  //
  // settings.voiceLang.inheritsBase（「基礎聲音」）本身是個沒有主詞的名詞
  // 片語，不能單獨當一行輸出；它是要餵進 settings.voiceLang.readonly 的
  // {{lang}} 占位符當「值」用的，跟查到實際語言代碼（如 zh-TW）時走的是
  // 同一顆模板、只是 lang 換成這個字串。
  const voiceLangText = useMemo(() => {
    if (characters === null) {
      return null;
    }
    const current = characters.find((c) => c.conf_uid === confUid);
    // 角色若明確設了發聲語言（角色分頁的 voiceLang，寫在 tts_config 的
    // text_lang），那才是權威值。從語音名稱切前兩段（zh-TW-HsiaoChenNeural →
    // zh-TW）只是 edge_tts 的推斷——用 GPT-SoVITS 的角色根本沒有 voice，
    // 於是會顯示「基礎聲音」，而她其實講的是設定好的那個語言。
    const voice = current?.voice;
    const lang = current?.voice_lang
      || (voice ? voice.split('-').slice(0, 2).join('-') : t('settings.voiceLang.inheritsBase'));
    return t('settings.voiceLang.readonly', { lang });
  }, [characters, confUid, t]);

  // ---- Step 5：用其他語言發聲（寫 conf.yaml，經
  // api/translator-config.ts／use-translator-settings.ts）----
  const {
    config: translatorConfig,
    loadError: translatorLoadError,
    engineSaving,
    saveEngine,
  } = useTranslatorSettings(baseUrl, active);

  const engineCollection = useMemo(() => createListCollection({
    items: [
      { label: t('settings.translator.engineLlm'), value: 'llm' },
      { label: t('settings.translator.engineDeeplx'), value: 'deeplx' },
    ],
  }), [t]);

  // 引擎切換：兩個選項都不需要憑證就能動作（deeplx 只是一個網址，已經有預設
  // 值），不用像 asr.tsx 的 groq/azure 那樣先當草稿——選了就立刻送出，效果
  // 同 asr.tsx 的 sherpa_onnx／faster_whisper 分支。deeplx_endpoint 這裡不帶，
  // 讓 saveEngine 用目前已知的值原樣回填（見 use-translator-settings.ts 的
  // save() 呼叫 buildTranslatorSavePayload 的說明），不因為切換引擎就意外
  // 改動它。
  const engineSaver = useAutosave(async (engine: TranslatorEngine) => {
    const result = await saveEngine(engine);
    return result.ok
      ? { ok: true } as const
      : { ok: false, error: result.error || t('settings.translator.saveFailed') } as const;
  }, { delayMs: 0 });

  const handleEngineChange = useCallback((value: string[]) => {
    const engine = value[0];
    if (!engine || (engine !== 'llm' && engine !== 'deeplx')) return;
    engineSaver.change(engine as TranslatorEngine);
  }, [engineSaver]);

  // DeepLX 位址：停手或離開欄位才存（不逐鍵送出）。草稿只在
  // 「使用者還沒開始編輯」時跟著後端值刷新（用 ref 記錄上一次同步進來的值，
  // 判斷草稿是否還等於它），理由跟 asr.tsx 的 azureRegion 同步邏輯一样，
  // 避免打字打到一半被背景刷新蓋掉。
  const [deeplxEndpointDraft, setDeeplxEndpointDraft] = useState('');
  const deeplxEndpointSyncedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!translatorConfig) return;
    if (
      deeplxEndpointSyncedRef.current === null
      || deeplxEndpointDraft === deeplxEndpointSyncedRef.current
    ) {
      setDeeplxEndpointDraft(translatorConfig.deeplx_endpoint);
      deeplxEndpointSyncedRef.current = translatorConfig.deeplx_endpoint;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [translatorConfig?.deeplx_endpoint]);

  const deeplxSaver = useAutosave(async (draft: string) => {
    const endpoint = draft.trim();
    const result = await saveEngine('deeplx', endpoint);
    if (!result.ok) {
      return { ok: false, error: result.error || t('settings.translator.saveFailed') } as const;
    }
    deeplxEndpointSyncedRef.current = endpoint;
    return { ok: true } as const;
  }, { validate: (draft) => (draft.trim() ? null : t('settings.translator.endpointEmpty')) });

  return (
    <Stack gap={4} pt={3} borderTopWidth="1px" borderColor="whiteAlpha.200">
      <Heading size="sm">{t('settings.user.sectionTitle')}</Heading>
      {/* 常駐提示（不是 toast）：這個區塊每一項都即時生效，不受 general.tsx
          下面的 TabActions 套用／還原控制——跟 asr.tsx 的 asrEngineSectionNote
          同一種道理、同一種呈現方式，理由見該檔案跟本檔檔頭註解。 */}
      <Text fontSize="xs" color="blue.300">{t('settings.user.sectionNote')}</Text>

      <InputField
        label={t('settings.user.displayName')}
        value={displayName}
        onChange={(value) => {
          setDisplayName(value);
          notifyLocalStorageChange(USER_DISPLAY_NAME_KEY, value);
        }}
      />
      <Text fontSize="xs" color="whiteAlpha.600">{t('settings.user.displayNameHelp')}</Text>

      <Field
        label={t('settings.user.chooseAvatar')}
      >
        <HStack>
          <input
            ref={avatarInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = '';
              if (file) handleAvatarFile(file);
            }}
          />
          <Button size="xs" variant="outline" onClick={() => avatarInputRef.current?.click()}>
            {t('settings.user.chooseAvatar')}
          </Button>
          {avatarDataUrl && (
            <>
              <img
                src={avatarDataUrl}
                alt=""
                style={{
                  width: 24, height: 24, borderRadius: '50%', objectFit: 'cover',
                }}
              />
              <Button
                size="xs"
                variant="ghost"
                onClick={() => {
                  setAvatarDataUrl('');
                  notifyLocalStorageChange(USER_AVATAR_KEY, '');
                }}
              >
                {t('settings.user.clearAvatar')}
              </Button>
            </>
          )}
        </HStack>
      </Field>
      <Text fontSize="xs" color="whiteAlpha.600">{t('settings.user.avatarHelp')}</Text>
      {avatarError && (
        <Text fontSize="xs" color="red.300">{avatarError}</Text>
      )}

      {/* 玩家語言：跟 general 分頁既有的 UI 顯示語言切換是兩回事——那個純前端、
          立即生效，這個寫 conf.yaml、需重啟後端才生效，且是告訴 AI「你說什麼
          語言」而非介面文字用哪種語言。help 文案就是用來區分兩者的，這裡用
          常駐 Text 而不是 hover-only 的 tooltip，避免使用者略過。 */}
      {/* 存檔這段 await 期間鎖住下拉選單，避免使用者連續切換造成請求互相
          競速——跟 general.tsx 的背景圖片上傳同一種做法（bgUploading 時
          opacity+pointerEvents 鎖住）。 */}
      <Box
        opacity={languageSaver.state.phase === 'saving' ? 0.5 : 1}
        pointerEvents={languageSaver.state.phase === 'saving' ? 'none' : 'auto'}
      >
        <SelectField
          label={t('settings.playerLanguage.label')}
          value={playerLang ? [playerLang] : []}
          onChange={handleLanguageChange}
          collection={languageCollection}
          placeholder={t('settings.playerLanguage.label')}
        />
      </Box>
      <SaveStatus state={languageSaver.state} />
      <Text fontSize="xs" color="whiteAlpha.600">{t('settings.playerLanguage.help')}</Text>
      {languageLoadError && (
        <Text fontSize="xs" color="red.300">{languageLoadError}</Text>
      )}

      <Field
        label={t('settings.playerPrompt.label')}
      >
        <Textarea
          rows={4}
          value={promptDraft}
          onChange={(e) => { setPromptDraft(e.target.value); promptSaver.change(e.target.value); }}
          onBlur={promptSaver.flush}
          placeholder={t('settings.playerPrompt.placeholder')}
          disabled={!promptLoaded}
        />
      </Field>
      <Text fontSize="xs" color="whiteAlpha.600">{t('settings.playerPrompt.help')}</Text>
      {promptLoadError && (
        <Text fontSize="xs" color="red.300">{promptLoadError}</Text>
      )}
      <SaveStatus state={promptSaver.state} />

      {/* Step 4：唯讀，沒有存檔動作。voiceLangText 在 pending／fetch 失敗時是
          null，這裡就整段不畫，不留一句沒查到東西卻語氣篤定的假宣稱。 */}
      {voiceLangText && (
        <Text fontSize="xs" color="whiteAlpha.600">{voiceLangText}</Text>
      )}

      {/* Step 5：用其他語言發聲＋字幕翻譯。獨立邊框分隔＋自己的 Heading，跟
          Step 1-4 用同一顆常駐 sectionNote 分開強調一次「這裡也是即時存檔、
          不受 TabActions 管」——這個子區塊比其他幾個複雜（有自己的載入狀態、
          兩種引擎、字幕語言），值得有自己的視覺分隔，不然使用者容易把它跟
          上面的玩家語言／全域指示混成同一組。 */}
      <Stack gap={2} pt={3} borderTopWidth="1px" borderColor="whiteAlpha.200">
        <Heading size="sm">{t('settings.translator.sectionTitle')}</Heading>
        <Text fontSize="xs" color="blue.300">{t('settings.translator.autoHint')}</Text>

        {translatorLoadError && (
          <Text fontSize="sm" color="red.300">{translatorLoadError}</Text>
        )}
        {!translatorLoadError && !translatorConfig && (
          <Text fontSize="sm" color="whiteAlpha.700">{t('settings.perf.loading')}</Text>
        )}

        {translatorConfig && (
          <>
            <Box opacity={engineSaving ? 0.5 : 1} pointerEvents={engineSaving ? 'none' : 'auto'}>
              <SaveStatus state={engineSaver.state} />
              <SelectField
                label={t('settings.translator.engine')}
                value={[translatorConfig.engine]}
                onChange={handleEngineChange}
                collection={engineCollection}
                placeholder={t('settings.translator.engine')}
              />
            </Box>
            <Text fontSize="xs" color="whiteAlpha.600">
              {translatorConfig.engine === 'deeplx'
                ? t('settings.translator.engineDeeplxHelp')
                : t('settings.translator.engineLlmHelp')}
            </Text>

            {translatorConfig.engine === 'deeplx' && (
              <Stack gap={2}>
                <InputField
                  label={t('settings.translator.deeplxEndpoint')}
                  value={deeplxEndpointDraft}
                  onChange={(value) => { setDeeplxEndpointDraft(value); deeplxSaver.change(value); }}
                  onBlur={deeplxSaver.flush}
                  help={t('settings.translator.deeplxEndpointHelp')}
                />
                <SaveStatus state={deeplxSaver.state} />
              </Stack>
            )}

            {/* 沒有這顆按鈕的話，翻譯壞掉跟翻譯關掉在畫面上完全一樣：角色照講、
                沒有錯誤、設定看起來也對。跑一次真的翻譯是唯一分得出來的辦法。 */}
            <HStack>
              <Button
                size="xs"
                variant="outline"
                onClick={handleTestTranslator}
                loading={testing}
                {...settingStyles.settingUI.footerButton}
              >
                {t('settings.translator.testButton')}
              </Button>
            </HStack>
            {testResult && (
              <Text
                fontSize="xs"
                color={testResult.ok ? 'green.300' : 'orange.300'}
                whiteSpace="pre-line"
              >
                {testResult.ok
                  ? t('settings.translator.testOk', {
                    result: testResult.result,
                    seconds: testResult.seconds,
                  })
                  : t(`settings.translator.testFail_${testResult.reason}`, {
                    error: testResult.error || '',
                  })}
              </Text>
            )}
          </>
        )}
      </Stack>
    </Stack>
  );
}

export default You;
