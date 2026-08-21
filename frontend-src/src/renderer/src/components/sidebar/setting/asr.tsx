/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable react/require-default-props */
// asr 分頁：這裡曾經只有前端的麥克風／VAD 設定（純 localStorage，不碰後端），
// 後端的辨識引擎選擇被埋在 perf 分頁裡——perf_route.py 自己的 docstring 都在
// 抱怨這個混淆（「the existing "ASR" settings tab is CLIENT-SIDE VAD/mic only
// —— it does NOT touch the backend engine」）。這次把引擎選擇搬回這個主題分頁，
// 所以畫面上刻意分成兩個獨立區塊、各自一個 Heading，把「這是本機瀏覽器設定」
// 跟「這是後端辨識引擎」講清楚，不然搬家等於把同一個混淆換個地方重演一次。
//
// 三種存檔機制在這個分頁裡共存，各自有訊號告訴使用者屬於哪一種：
//
// 1. 麥克風／VAD（上半部）：分頁自己的套用／還原按鈕（見下面的 ），
//    按下「套用」才會寫進 localStorage；「還原」把草稿還原成原值。ASRProps
//    只保留 onCancel——外層抽屜開合時仍會呼叫它把草稿還原，但儲存已經不再
//    由抽屜驅動。這個區塊自己的按鈕就放在這個小節結尾，緊接在 VAD 欄位
//    之後、引擎選擇區塊之前。
// 2. 引擎下拉選單（下半部）：只有 sherpa_onnx_asr／faster_whisper 兩個不需要
//    憑證的選項才會「切換當下」即時打 API（跟 perf.tsx 的 keep_alive 模式
//    同一種模式）。
// 3. 需要憑證的雲端引擎（groq_whisper_asr／azure_asr）：選了不會立刻送出，
//    只是记成本機草稿（pendingEngine），必须連同憑證一起按下面的「儲存」
//    才會真的寫進 conf.yaml——原因見 handleEngineChange 旁的說明：如果選了
//    就送，conf.yaml 的 asr_model 可能指到一個因為沒憑證而起不來的引擎，
//    跟這次任務要對 faster_whisper 誠實揭露的「靜默 fallback」是同一種問題，
//    不能在這裡重演。
//
// 下半部整個區塊在 Heading 底下有一段常駐文字（asrEngineSectionNote）講「這裡
// 自己存檔、不受下面 Save/Cancel 影響」；還沒送出的雲端引擎選擇會顯示
// asrEnginePendingNotice（「尚未儲存，仍在用 X」）——這兩段都是常駐文字，不是
// 會消失的 toast，因為「這格到底歸誰管」跟「現在到底存了沒」都是使用者需要
// 隨時看得到、而不是操作當下才看得到一次的資訊。
import {
  useState, useEffect, useCallback, useMemo,
} from 'react';
// 遷移中：表單控制項已改用 Ark UI + Tailwind（common-tw），版面容器與下半部的
// ASR 引擎區塊仍是 Chakra。createListCollection 直接從 Ark 拿——Chakra 現在是把
// Ark 的原樣 re-export（它把 Ark 釘在同一版），型別剛好相容，但那是巧合而不是
// 契約，拔掉 Chakra 時就會斷。
import { Stack, Text, Heading, Collapsible } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useTranslation } from 'react-i18next';
import { HiChevronDown, HiChevronRight } from 'react-icons/hi';
import { settingStyles } from './setting-styles';
import { useASRSettings } from '@/hooks/sidebar/setting/use-asr-settings';
// micOn 不在 useASRSettings 裡（那個 hook 只管三個自動行為），模式選單要
// 同時讀寫麥克風本身的開關，所以直接拿 VAD context。startMic／stopMic 才是
// 真正開關 VAD 實例的入口，setMicOn 只改旗標——見 applyMicMode 的說明。
import { useVAD } from '@/context/vad-context';
import { useAiState } from '@/context/ai-state-context';
import {
  resolveMicMode, micModeState, type NamedMicMode,
} from '@/services/mic-mode';
import {
  SwitchField, NumberField, SelectField, InputField, } from './common';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import {
  fetchPerf,
  setAsrModel,
  setAsrCredentials,
  type PerfState,
  type AsrSaveResult,
} from '@/api/perf.ts';

interface ASRProps {
  // 這個分頁目前是不是使用者看得到的那個 tab（setting-ui.tsx 依 activeTab 算出）。
  // 用來在套用 perf 的一鍵模式後，使用者切回這個分頁時重新拉一次現值——見下面
  // 第二個 fetchPerf effect 的說明。預設 true：萬一哪天有別的呼叫端沒傳這個
  // prop（目前只有 setting-ui.tsx 一處註冊），行為退回「一律當作可見」，不會
  // 因為漏傳就悄悄不刷新。
  active?: boolean
}

// 後端引擎的下拉選單文案有專屬 i18n 鍵（不是後端傳什麼字串就原樣顯示）——
// 跟 perf.tsx 的 presetNameKey 同一個理由：後端 ASR_MODELS 裡的值
// （sherpa_onnx_asr／faster_whisper／...）不是給使用者看的文案。這幾個鍵
// 已經在 settings.perf 命名空間裡、五語言都翻好了（perf.tsx 那次任務先寫的，
// 只是還沒有 UI 用它們），這裡直接沿用，不重複造一份 settings.asr 底下的
// 同義鍵。找不到對應鍵時（asr_models 出現未知值）直接顯示原始字串。
function asrModelLabelKey(name: string): string | null {
  if (name === 'sherpa_onnx_asr') return 'settings.perf.asrSherpa';
  if (name === 'faster_whisper') return 'settings.perf.asrFasterWhisper';
  if (name === 'groq_whisper_asr') return 'settings.perf.asrGroq';
  if (name === 'azure_asr') return 'settings.perf.asrAzure';
  return null;
}

// 這兩個引擎沒有憑證就跑不起來——service_context.init_asr 找不到可用憑證會
// 初始化失敗，下次重啟靜默 fallback 回 sherpa_onnx（跟 faster_whisper 缺相依
// 套件時的行為一樣）。選到這兩個值絕不能立刻送出，見 handleEngineChange。
const CREDENTIAL_ENGINES = new Set(['groq_whisper_asr', 'azure_asr']);

function ASR({active = true}: ASRProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { confName } = useConfig();
  const {
    localSettings,
    autoStopMic,
    autoStartMicOn,
    autoStartMicOnConvEnd,
    setAutoStopMic,
    setAutoStartMicOn,
    setAutoStartMicOnConvEnd,
    handleInputChange,
  } = useASRSettings();
  const { micOn, startMic, stopMic } = useVAD();
  const { aiState, setAiState } = useAiState();
  const [micAdvancedOpen, setMicAdvancedOpen] = useState(false);

  // 改成即時生效之後沒有草稿可還原，onCancel 的登記整段移除。
  // 麥克風模式：三個布林值的組合換算成一個模式，規則見 services/mic-mode.ts。
  // 使用者手動改下面的進階開關、改出不屬於任何模式的組合時會回 'custom'，
  // 選單就顯示「自訂」——不能繼續掛著一個已經不成立的模式名稱。
  const micState = { micOn, autoStopMic, autoStartMicOn, autoStartMicOnConvEnd };
  const micMode = resolveMicMode(micState);

  const applyMicMode = useCallback(async (mode: NamedMicMode) => {
    const next = micModeState(mode);
    // 三個自動行為純粹是旗標，直接設。
    setAutoStopMic(next.autoStopMic);
    setAutoStartMicOn(next.autoStartMicOn);
    setAutoStartMicOnConvEnd(next.autoStartMicOnConvEnd);

    // micOn 不能用 setMicOn 直接設。沒有任何 effect 在監看 micOn——真正
    // 建立／銷毀 VAD 實例的是 startMic／stopMic，setMicOn 只是它們順手更新
    // 的旗標。只改旗標的話畫面會顯示「完全不開」但麥克風其實還在收音，
    // 而且照樣會跳「沒聽清楚，再說一次？」（onVADMisfire 仍然掛著）。
    // 收拾 aiState 的方式跟 use-mic-toggle.ts 一致。
    if (next.micOn && !micOn) {
      await startMic();
    } else if (!next.micOn && micOn) {
      stopMic();
      if (aiState === 'listening') setAiState('idle');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [micOn, autoStopMic, autoStartMicOn, autoStartMicOnConvEnd, aiState,
    startMic, stopMic, setAiState,
    setAutoStopMic, setAutoStartMicOn, setAutoStartMicOnConvEnd]);

  // 'custom' 只在真的處於自訂狀態時才出現在清單裡——平常讓它佔一個選項，
  // 使用者會以為那是一個可以主動選的模式，但它沒有對應的設定可套。
  const micModeCollection = useMemo(() => createListCollection({
    items: [
      { value: 'always', label: t('settings.asr.micModeAlways') },
      { value: 'vad', label: t('settings.asr.micModeVad') },
      { value: 'push', label: t('settings.asr.micModePush') },
      ...(micMode === 'custom'
        ? [{ value: 'custom', label: t('settings.asr.micModeCustom') }]
        : []),
    ],
  }), [t, micMode]);


  // ---- 後端辨識引擎（本任務新增）----
  const [perf, setPerf] = useState<PerfState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [engineSaving, setEngineSaving] = useState(false);

  // 只在目前這個角色真的釘了引擎時才警告，理由同 tts.tsx。
  const asrCharacterOverride = perf?.engine_overrides_by_character?.[confName]?.asr_model
    || null;

  // 選了 groq/azure 但還沒連同憑證送出時的本機草稿——不是 null 就代表「畫面
  // 上選的引擎」跟「conf.yaml 現在真正生效的引擎」（perf.asr_model）不一致，
  // 下面的 displayedEngine／asrEnginePendingNotice 都是為了讓這個落差對使用者
  // 可見。見 handleEngineChange／handleSaveCredentials 的說明。
  const [pendingEngine, setPendingEngine] = useState<string | null>(null);

  // 雲端金鑰欄位：從掛載到現在只被使用者的 onChange 賦值過，絕對不會被
  // fetchPerf() 的回應（groq_api_key_masked／azure_api_key_masked）指派——
  // 這是「遮罩字串絕不可能流進送出 payload」的第一道防線，見 api/perf.ts
  // 裡 setAsrCredentials 上方的說明。azureRegion 不是密鑰，可以放心用伺服器
  // 回傳的明碼值初始化。
  const [groqApiKey, setGroqApiKey] = useState('');
  const [azureApiKey, setAzureApiKey] = useState('');
  const [azureRegion, setAzureRegion] = useState('');
  const [savingCreds, setSavingCreds] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchPerf(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setPerf(result.data);
        setAzureRegion(result.data.azure_region || '');
      } else {
        setLoadError(result.error || t('settings.perf.loadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl]);

  // 套用 perf 分頁的一鍵模式（或直接呼叫 /api/perf/preset）之後，這個分頁如果
  // 早就掛載著（Chakra 的 Tabs.Content 預設不做 lazyMount，抽屜一打開三個分頁
  // 就都掛了），畫面上顯示的引擎會停在套用前抓到的那份、再也不會自動更新——
  // 使用者切回這個分頁時看到的是一個後端已經不再使用的引擎，跟這整個任務要
  // 防的「畫面顯示的引擎其實沒在跑」是同一種破綻，只是從 preset 這個新門進來。
  // 見任務簡報 Fix 1。
  //
  // 修法：使用者切回這個分頁（active 從 false 變 true）時重新打一次
  // GET /api/perf。不能整份覆寫目前的畫面狀態——這裡有兩種未存檔的草稿：
  // 1) pendingEngine（選了 groq/azure 但還沒按儲存）與 groqApiKey／azureApiKey
  //    （半打的憑證）：這三個 state 完全不在這個 effect 的寫入範圍內，重新整理
  //    不會碰到它們，草稿原封不動留著、待存的提示（asrEnginePendingNotice）也
  //    還在——只是它引用的 currentEngineLabel 會因為 perf.asr_model 更新而跟著
  //    修正，這正好把任務簡報點名的「pending notice 的 {{current}} 也會跟著
  //    perf 分頁的套用而過期」一併解掉，不需要另外寫一套機制。
  // 2) azureRegion：這個欄位不是憑證，明碼往返、可以直接拿伺服器值初始化，但
  //    使用者可能正在編輯它（還沒按儲存）。用「目前草稿是否還等於上一次載入
  //    的伺服器值」判斷有沒有在編輯中——沒異動就跟著刷新，有異動（使用者正在
  //    打字）就不覆寫,把使用者半打的文字保留下來。
  //
  // 讀取失敗時故意不設 loadError／不顯示任何東西：這只是背景刷新，失敗了維持
  // 原本已經在畫面上、能動作的那份資料，好過因為一次背景刷新失敗就把整個分頁
  // 換成錯誤畫面。
  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    (async () => {
      const result = await fetchPerf(baseUrl);
      if (cancelled || !result.ok) return;
      const data = result.data;
      setAzureRegion((prevRegion) => (
        perf && prevRegion !== (perf.azure_region || '')
          ? prevRegion
          : (data.azure_region || '')
      ));
      setPerf(data);
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, baseUrl]);

  const engineCollection = useMemo(() => createListCollection({
    items: (perf?.asr_models ?? []).map((name) => {
      const key = asrModelLabelKey(name);
      return { label: key ? t(key) : name, value: name };
    }),
  }), [perf?.asr_models, t]);

  // 畫面上「選單顯示的引擎」：有未送出的草稿就顯示草稿，否則顯示 conf.yaml
  // 現在真正生效的引擎。憑證欄位的顯示／隱藏也跟著這個值走，而不是
  // perf.asr_model——這樣選了 groq 之後憑證欄位要立刻出現讓使用者輸入，不用
  // 等存檔成功才看得到。
  const displayedEngine = pendingEngine ?? perf?.asr_model ?? '';

  const currentEngineLabel = useMemo(() => {
    if (!perf) return '';
    const key = asrModelLabelKey(perf.asr_model);
    return key ? t(key) : perf.asr_model;
  }, [perf, t]);

  // POST /api/perf/asr 的回應永遠是「現在的完整 asr 狀態」（含仍是遮罩過的
  // 金鑰），不管這次送的是引擎還是憑證——把它整份寫回 perf state，兩個存檔
  // 路徑（引擎切換／憑證儲存）都呼叫這個函式，不重複組裝欄位。
  const applySaveResult = useCallback((data: AsrSaveResult) => {
    setPerf((p) => (p ? {
      ...p,
      asr_model: data.asr_model,
      groq_api_key_masked: data.groq_api_key_masked,
      azure_api_key_masked: data.azure_api_key_masked,
      azure_region: data.azure_region,
    } : p));
    setAzureRegion(data.azure_region || '');
  }, []);

  // 下拉選單切換時：
  // - 選回目前已生效的引擎：沒有東西要存，只是清掉可能殘留的草稿。
  // - 選到 groq/azure：不能立刻送出。這兩個引擎沒有憑證就跑不起來，如果現在
  //   立刻 POST，conf.yaml 的 asr_model 會被改成一個可能因為缺憑證而初始化
  //   失敗的引擎——service_context.init_asr 失敗會在下次重啟靜默 fallback回
  //   sherpa_onnx，畫面卻還顯示使用者選的那個雲端引擎，變成「選了但沒在用、
  //   沒人告訴你」。這正是這次任務要對 faster_whisper 誠實揭露的同一種
  //   靜默 fallback，不能在這裡重演一次。所以先當成本機草稿（pendingEngine），
  //   等使用者在下面按「儲存」、把引擎和憑證包在同一次 POST 送出（見
  //   handleSaveCredentials），conf.yaml 才會被改——那個函式會擋下「還沒有
  //   任何可用憑證」的送出，見它旁邊的 disabled 判斷。
  // - 選到 sherpa_onnx_asr／faster_whisper：兩個都不需要憑證，切換當下就能
  //   真的動作，沿用即時存檔（跟 perf.tsx 的 keep_alive 模式同一種模式）。
  const handleEngineChange = useCallback(async (value: string[]) => {
    const model = value[0];
    if (!model || !perf) return;

    if (model === perf.asr_model) {
      setPendingEngine(null);
      return;
    }

    if (CREDENTIAL_ENGINES.has(model)) {
      setPendingEngine(model);
      return;
    }

    setPendingEngine(null);
    setEngineSaving(true);
    const result = await setAsrModel(baseUrl, model);
    setEngineSaving(false);
    if (result.ok) {
      applySaveResult(result.data);
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
  }, [baseUrl, perf, applySaveResult, t]);

  // 憑證是文字輸入框，不做每個按鍵都送出——跟 perf.tsx 的自訂 keep_alive 秒數
  // 同一種模式，要有明確的「儲存」按鈕使用者才知道自己送出了什麼。
  //
  // 有 pendingEngine（使用者選了一個還沒送出的 groq/azure）時，這次連同
  // asr_model 一起送——這是唯一允許 conf.yaml 的 asr_model 被改成 groq/azure
  // 的路徑，確保送出去的當下引擎一定跟著憑證（新打的，或先前已經存過、
  // 現在只是切回去用的都算，見下面 Save 按鈕的 disabled 判斷），不會出現
  // 「引擎已切但沒憑證」的中間狀態。
  //
  // 沒有 pendingEngine（已經是目前生效的雲端引擎，只是要更新金鑰／region）
  // 時，只送有異動的欄位：groq 只在金鑰欄位非空白時才送；azure 的 region
  // 不是密鑰，一律送出（就算跟現值相同也是無害的原樣寫回），金鑰欄位一樣
  // 只在非空白時才送。
  const handleSaveCredentials = useCallback(async () => {
    if (!perf) return;
    const engine = pendingEngine ?? perf.asr_model;
    const payload: {
      asr_model?: string
      groq_api_key?: string
      azure_api_key?: string
      azure_region?: string
    } = {};
    if (pendingEngine) payload.asr_model = pendingEngine;
    if (engine === 'groq_whisper_asr' && groqApiKey.trim()) {
      payload.groq_api_key = groqApiKey.trim();
    }
    if (engine === 'azure_asr') {
      // 第二道防線（第一道是下面 azureSaveDisabled 把按鈕擋住）：region 是
      // Azure 的必填欄位之一，空字串一樣會被後端當成「有帶」寫入（見
      // azureSaveDisabled 旁邊的說明），絕不能送出空字串。就算按鈕的
      // disabled 判斷哪天被改壞，這裡還是會擋下。
      if (!azureRegion.trim()) return;
      if (azureApiKey.trim()) payload.azure_api_key = azureApiKey.trim();
      payload.azure_region = azureRegion.trim();
    }
    if (Object.keys(payload).length === 0) return;

    setSavingCreds(true);
    const result = await setAsrCredentials(baseUrl, payload);
    setSavingCreds(false);
    if (result.ok) {
      applySaveResult(result.data);
      setPendingEngine(null);
      // 存檔成功後清空草稿：欄位重新顯示 placeholder（已設定），不留著
      // 剛送出的明碼字串——即使 type="password" 已經擋住肉眼看見，清空
      // 也讓「有沒有真的存到」這件事有個看得出來的畫面變化。
      setGroqApiKey('');
      setAzureApiKey('');
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
  }, [baseUrl, perf, pendingEngine, groqApiKey, azureApiKey, azureRegion, applySaveResult, t]);

  // 「儲存」按鈕是否可按：有沒有一個可用的憑證來源（這次打的新字，或先前已經
  // 存過、還留在 conf.yaml 裡的舊金鑰——後者用 *_api_key_masked 是否非空判斷）。
  // 沒有任何一種來源時擋下送出：這正是要防的事故本身——按下去只會把 asr_model
  // 改成一個沒有憑證可用的引擎。pendingEngine 存在時，只要有憑證來源就視為
  // 「有事要存」（引擎本身就是要送出的變更）；沒有 pendingEngine（已經是目前
  // 生效的引擎，只是想換金鑰／region）時，維持原本「真的打了新字／region 有
  // 改動」才讓按鈕可按的判斷，不要讓使用者誤按到一個什麼都没變的儲存。
  const hasGroqCredentialSource = Boolean(groqApiKey.trim()) || Boolean(perf?.groq_api_key_masked);
  const hasAzureCredentialSource = Boolean(azureApiKey.trim()) || Boolean(perf?.azure_api_key_masked);

  // Groq 只需要一把金鑰（見 asr/groq_whisper_asr.py 的 VoiceRecognition.__init__，
  // 參數只有 api_key／model／lang，後兩者都有預設值）——上面的
  // hasGroqCredentialSource 已經是完整的必要條件，沒有 region 這種第二個必填
  // 欄位需要另外把關，這裡不需要類似 hasAzureRegion 的判斷。
  const groqSaveDisabled = pendingEngine === 'groq_whisper_asr'
    ? !hasGroqCredentialSource
    : !groqApiKey.trim();

  // Azure 除了金鑰還需要 region——asr/azure_asr.py 的 VoiceRecognition.__init__
  // 是 `if not subscription_key or not region: raise ValueError(...)`，兩個
  // 都是必填。handleSaveCredentials 無條件送出 azure_region（即使是空字串，
  // 見該函式旁的說明：region 不是密鑰，一律送出），而 perf_route.py 把非
  // None 的字串（包含空字串）視為「有帶」就寫入——這代表如果只擋了金鑰、
  // 沒擋 region，使用者可以在 region 留空的情況下把 conf.yaml 的 region
  // 清空／覆寫成空字串，效果跟完全沒有憑證一樣：下次重啟 init_asr 建立
  // VoiceRecognition 會丟 ValueError，靜默 fallback 回 sherpa_onnx——這正是
  // 這一整輪要防的同一種事故，只是換了 region 這個閘門被漏掉。所以這裡
  // 對 pendingEngine／非 pendingEngine 兩種情況都額外要求 hasAzureRegion，
  // 不只是「有沒有異動」，是「送出的當下 region 欄位是不是空的」——就算是
  // 已經生效的 azure 引擎、只是想換金鑰，也不能讓使用者不小心把 region
  // 欄位清空還能按下儲存。
  const hasAzureRegion = Boolean(azureRegion.trim());

  const azureCredsUnchanged = Boolean(
    perf
    && !pendingEngine
    && !azureApiKey.trim()
    && azureRegion.trim() === (perf.azure_region || '').trim(),
  );
  const azureSaveDisabled = (
    pendingEngine === 'azure_asr' ? !hasAzureCredentialSource : azureCredsUnchanged
  ) || !hasAzureRegion;

  return (
    <Stack {...settingStyles.common.container}>
      {/* 麥克風與語音偵測：純前端 localStorage，見檔頭說明。 */}
      <Stack gap={2}>
        <Heading size="sm">{t('settings.asr.micVadSectionTitle')}</Heading>
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.asr.micVadSectionDesc')}</Text>

        <SelectField
          label={t('settings.asr.micModeLabel')}
          value={[micMode]}
          onChange={(value) => {
            const picked = value[0];
            // 'custom' 沒有對應的設定可套，選到它就當作沒選（它只是用來
            // 誠實顯示目前狀態，不是一個可以主動切過去的模式）。
            if (picked && picked !== 'custom') applyMicMode(picked as NamedMicMode);
          }}
          collection={micModeCollection}
        />
        <Text fontSize="xs" color="whiteAlpha.600">
          {t(`settings.asr.micModeDesc.${micMode}`)}
        </Text>

        {/* 進階：三個原始開關原樣保留，只是收起來。模式選單涵蓋得了的是常
            用的三種組合，剩下十幾種不是錯的、只是沒有名字——移除它們是閹割
            不是精簡（同 memory.tsx 進階區的判斷）。 */}
        <Collapsible.Root
          open={micAdvancedOpen}
          onOpenChange={(details) => setMicAdvancedOpen(details.open)}
        >
          <Collapsible.Trigger asChild>
            <Button size="xs" variant="ghost">
              {micAdvancedOpen ? <HiChevronDown /> : <HiChevronRight />}
              {t('settings.asr.micAdvancedToggle')}
            </Button>
          </Collapsible.Trigger>
          <Collapsible.Content>
            <Stack gap={2} mt={2}>
              <Text fontSize="xs" color="whiteAlpha.500">
                {t('settings.asr.micAdvancedHint')}
              </Text>

              <SwitchField
                label={t('settings.asr.autoStopMic')}
                checked={autoStopMic}
                onChange={setAutoStopMic}
              />

              <SwitchField
                label={t('settings.asr.autoStartMicOnConvEnd')}
                checked={autoStartMicOnConvEnd}
                onChange={setAutoStartMicOnConvEnd}
              />

              <SwitchField
                label={t('settings.asr.autoStartMicOn')}
                checked={autoStartMicOn}
                onChange={setAutoStartMicOn}
              />
            </Stack>
          </Collapsible.Content>
        </Collapsible.Root>

        <NumberField
          label={t('settings.asr.positiveSpeechThreshold')}
          help={t('settings.asr.positiveSpeechThresholdDesc')}
          value={localSettings.positiveSpeechThreshold}
          onChange={(value) => handleInputChange('positiveSpeechThreshold', value)}
          min={1}
          max={100}
        />

        <NumberField
          label={t('settings.asr.negativeSpeechThreshold')}
          help={t('settings.asr.negativeSpeechThresholdDesc')}
          value={localSettings.negativeSpeechThreshold}
          onChange={(value) => handleInputChange('negativeSpeechThreshold', value)}
          min={0}
          max={100}
        />

        <NumberField
          label={t('settings.asr.redemptionFrames')}
          help={t('settings.asr.redemptionFramesDesc')}
          value={localSettings.redemptionFrames}
          onChange={(value) => handleInputChange('redemptionFrames', value)}
          min={1}
          max={100}
        />

        {/* 誤觸時的調參建議以前印在字幕上——三行術語蓋在角色臉上，而且是在使用者
            離這三個旋鈕最遠的時候講的。它屬於這裡。 */}
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.asr.vadTuningHint')}</Text>
      </Stack>

      {/* 後端辨識引擎：見檔頭說明，三種存檔機制之二／之三都在這裡。 */}
      <Stack gap={2}>
        <Heading size="sm">{t('settings.perf.asrSectionTitle')}</Heading>
        {/* 常駐提示（不是 toast）：這個區塊自己存檔，不受外層抽屜 Save/Cancel
            影響——分頁裡同時存在三種存檔機制，光靠操作當下彈出的 toast 不夠，
            使用者需要隨時能看到「這格歸誰管」。 */}
        <Text fontSize="xs" color="blue.300">{t('settings.perf.asrEngineSectionNote')}</Text>
        {/* 角色檔自己的 asr_config 會蓋掉這裡選的引擎，跟 tts.tsx 同一個
            陷阱——選了、存了、卻沒有生效，畫面上卻沒有任何線索。 */}
        {asrCharacterOverride && (
          <Text fontSize="xs" color="orange.300">
            {t('settings.perf.asrCharacterOverride', {
              character: confName,
              engine: asrCharacterOverride,
            })}
          </Text>
        )}
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.perf.asrEngineHelp')}</Text>

        {loadError && (
          <Text fontSize="sm" color="red.300">{loadError}</Text>
        )}

        {!loadError && !perf && (
          <Text fontSize="sm" color="whiteAlpha.700">{t('settings.perf.loading')}</Text>
        )}

        {perf && (
          <>
            <SelectField
              label={t('settings.perf.asrEngineLabel')}
              value={displayedEngine ? [displayedEngine] : []}
              onChange={handleEngineChange}
              collection={engineCollection}
              placeholder={t('settings.perf.asrEnginePlaceholder')}
            />
            {engineSaving && (
              <Text fontSize="xs" color="whiteAlpha.600">{t('settings.perf.applying')}</Text>
            )}
            {/* 常駐提示：選了 groq/azure 但還沒按下面的儲存——畫面上的選擇跟
                conf.yaml 現在真正生效的引擎不一樣，這件事必須隨時可見，不能只
                靠使用者自己記得。 */}
            {pendingEngine && (
              <Text fontSize="xs" color="orange.300">
                {t('settings.perf.asrEnginePendingNotice', { current: currentEngineLabel })}
              </Text>
            )}

            {/* 兩個雲端引擎需要憑證才能真正動作——依畫面上選到的引擎
                （displayedEngine，可能還只是草稿）顯示對應欄位。 */}
            {displayedEngine === 'groq_whisper_asr' && (
              <Stack gap={2}>
                <InputField
                  label={t('settings.perf.groqApiKeyLabel')}
                  value={groqApiKey}
                  onChange={setGroqApiKey}
                  type="password"
                  placeholder={
                    perf.groq_api_key_masked ? t('setup.keyAlreadySetPlaceholder') : undefined
                  }
                  help={t('settings.perf.groqApiKeyHelp')}
                />
                {/* 缺欄位有解釋，「沒有變更」沒有——按鈕一樣是暗的，使用者
                    一樣按不下去，卻看不到原因。跟 tts.tsx 的
                    ttsConfigUnchanged 是同一個缺口。 */}
                {!pendingEngine && !groqApiKey.trim() && (
                  <Text fontSize="xs" color="whiteAlpha.600">
                    {t('settings.perf.credsUnchanged')}
                  </Text>
                )}
                <Button
                  size="xs"
                  tone="blue"
                  onClick={handleSaveCredentials}
                  loading={savingCreds}
                  disabled={groqSaveDisabled}
                  className="self-start"
                >
                  {t('common.save')}
                </Button>
              </Stack>
            )}

            {displayedEngine === 'azure_asr' && (
              <Stack gap={2}>
                <InputField
                  label={t('settings.perf.azureApiKeyLabel')}
                  value={azureApiKey}
                  onChange={setAzureApiKey}
                  type="password"
                  placeholder={
                    perf.azure_api_key_masked ? t('setup.keyAlreadySetPlaceholder') : undefined
                  }
                  help={t('settings.perf.azureApiKeyHelp')}
                />
                <InputField
                  label={t('settings.perf.azureRegionLabel')}
                  value={azureRegion}
                  onChange={setAzureRegion}
                  help={t('settings.perf.azureRegionHelp')}
                />
                {/* 常駐提示，不是等使用者按下去才跳錯誤：region 留空時儲存
                    按鈕會被擋下（見 hasAzureRegion），沒有這行文字的話，
                    使用者只會看到一顆按不下去的按鈕、猜不到少填了什麼。 */}
                {!hasAzureRegion && (
                  <Text fontSize="xs" color="orange.300">
                    {t('settings.perf.azureRegionRequired')}
                  </Text>
                )}
                {hasAzureRegion && azureCredsUnchanged && (
                  <Text fontSize="xs" color="whiteAlpha.600">
                    {t('settings.perf.credsUnchanged')}
                  </Text>
                )}
                <Button
                  size="xs"
                  tone="blue"
                  onClick={handleSaveCredentials}
                  loading={savingCreds}
                  disabled={azureSaveDisabled}
                  className="self-start"
                >
                  {t('common.save')}
                </Button>
              </Stack>
            )}
          </>
        )}
      </Stack>
    </Stack>
  );
}

export default ASR;
