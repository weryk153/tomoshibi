/* eslint-disable import/no-extraneous-dependencies */
// tts 分頁：曾經整個檔案是 `return <Box> </Box>;`，但已經註冊在分頁列
// （setting-ui.tsx 用 <TTS />，無 props）——使用者點「合成」看到的是空白畫面，
// 這是 UI 上看得見的破綻。這裡補上語音合成引擎選擇，跟 asr.tsx 剛解決的是
// 同一種問題（同一個 perf_route.py 底下的姊妹端點 /api/perf/tts），照抄它
// 已經驗證過的形狀。
//
// TTS_MODELS 只有兩個值：edge_tts（內建，不需要任何設定）與 gpt_sovits_tts
// （需要 gpt_sovits_api_url／gpt_sovits_ref_audio_path 兩個欄位才能真正動
// 作）。如果選了 gpt_sovits_tts 就立刻送出，conf.yaml 的 tts_model 會指到
// 一個當下可能還沒設定服務位址／參考音檔的引擎——service_context.py:411-414
// 找不到可達的 GPT-SoVITS 服務會靜默 fallback 回 edge_tts，畫面卻還顯示
// gpt_sovits_tts，變成「選了但沒在用、沒人告訴你」。所以選到 gpt_sovits_tts
// 時只先記成本機草稿（pendingEngine），必須連同兩個欄位一起按下面的「儲存」
// 才會真的寫進 conf.yaml，見 handleEngineChange／handleSaveConfig。
//
// 跟 asr.tsx 不同的地方：gpt_sovits 的兩個欄位是 URL 與檔案路徑，不是憑證，
// perf_route.py 的 _tts_from_conf 原樣回傳明碼——不需要 asr.tsx 那套「遮罩
// 字串絕不可以流進送出 payload」的防線，可以直接用 fetchPerf 的回應初始化
// 輸入框（但仍要初始化，否則切換引擎會把使用者已經填好的值清空）。
//
// prompt_text／text_lang／prompt_lang 三個欄位：gpt_sovits_tts 共有九個設定，
// 原本 UI 只開放 api_url／ref_audio_path 兩個，缺了 prompt_text（參考音檔的
// 逐字稿）就等於功能沒辦法從 App 裡設完——GPT-SoVITS 靠它對齊「這段音檔說的
// 是這些字」，沒填克隆效果差或直接失敗。text_lang／prompt_lang 分別是角色
// 回覆的語言、參考音檔本身的語言，是真的使用者選擇，不是可以隨便留預設的
// 旋鈕。三者都不是密鑰，明碼往返安全，同上一段的理由。
//
// prompt_text 刻意不加進下面的 configSaveDisabled 必填閘門——它本來就是可選
// 欄位（conf.yaml 樣板註解標的是「可选」，不像 ref_audio_path／prompt_lang
// 標「必需」），留空只是克隆效果變差、不是整個引擎壞掉，用 gptSovitsPromptTextHelp
// 的常駐提示講清楚就好，不必攔住存檔。text_lang／prompt_lang 用下拉選單而非
// 自由輸入，值域是後端 GET /api/perf 回傳的 gpt_sovits_langs（perf_route.py
// 的 GPT_SOVITS_LANGS）——選單一律有預設值可選，不會出現「空著送出」的情況，
// 不需要額外的必填檢查。
//
// 這個分頁本身不接 onSave／onCancel（跟 about.tsx 一樣是無 props 的分頁），
// 存檔即時發生、不受外層抽屜的 Save/Cancel 影響——底下的常駐提示
// （ttsEngineSectionNote）把這件事講清楚，不是等使用者按錯才知道。
import {
  useState, useEffect, useCallback, useMemo,
} from 'react';
import { Stack, Text, Heading } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useTranslation } from 'react-i18next';
import { settingStyles } from './setting-styles';
import { SelectField, InputField } from './common';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { useConfig } from '@/context/character-config-context';
import {
  fetchPerf,
  setTtsModel,
  setTtsConfig,
  type PerfState,
  type TtsSaveResult,
} from '@/api/perf.ts';
import { gptSovitsLangLabelKey } from '@/utils/gpt-sovits-langs';
// 這個對照原本寫死在這裡，角色編輯器也要用，抽到 utils 共用避免兩份漂移。
import { ttsModelLabelKey } from '@/utils/tts-models';
import GptSovitsInstall from '@/components/llm/gpt-sovits-install';


// 這個引擎沒有 api_url／ref_audio_path 就跑不起來——service_context.py
// 找不到可達的服務會初始化失敗，下次重啟靜默 fallback 回 edge_tts（見檔頭
// 說明）。選到這個值絕不能立刻送出，見 handleEngineChange。
const NEEDS_CONFIG_ENGINE = 'gpt_sovits_tts';

interface TTSProps {
  // 這個分頁目前是不是使用者看得到的那個 tab（setting-ui.tsx 依 activeTab
  // 算出）。用來在套用 perf 的一鍵模式後，使用者切回這個分頁時重新拉一次
  // 現值——見下面第二個 fetchPerf effect 的說明，跟 asr.tsx 的 active prop
  // 同一個理由。預設 true：萬一哪天有別的呼叫端沒傳這個 prop（目前只有
  // setting-ui.tsx 一處註冊），行為退回「一律當作可見」。
  active?: boolean
}

function TTS({ active = true }: TTSProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const { confName } = useConfig();

  const [perf, setPerf] = useState<PerfState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [engineSaving, setEngineSaving] = useState(false);

  // 選了 gpt_sovits_tts 但還沒連同欄位送出時的本機草稿——不是 null 就代表
  // 「畫面上選的引擎」跟「conf.yaml 現在真正生效的引擎」（perf.tts_model）
  // 不一致，下面的 displayedEngine／ttsEnginePendingNotice 都是為了讓這個
  // 落差對使用者可見。見 handleEngineChange／handleSaveConfig 的說明。
  const [pendingEngine, setPendingEngine] = useState<string | null>(null);

  // 這幾個欄位不是憑證，直接用伺服器回傳的明碼值初始化，見檔頭說明。
  const [gptSovitsApiUrl, setGptSovitsApiUrl] = useState('');
  const [gptSovitsRefAudioPath, setGptSovitsRefAudioPath] = useState('');
  const [gptSovitsPromptText, setGptSovitsPromptText] = useState('');
  const [gptSovitsTextLang, setGptSovitsTextLang] = useState('');
  const [gptSovitsPromptLang, setGptSovitsPromptLang] = useState('');
  const [savingConfig, setSavingConfig] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchPerf(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setPerf(result.data);
        setGptSovitsApiUrl(result.data.gpt_sovits_api_url || '');
        setGptSovitsRefAudioPath(result.data.gpt_sovits_ref_audio_path || '');
        setGptSovitsPromptText(result.data.gpt_sovits_prompt_text || '');
        setGptSovitsTextLang(result.data.gpt_sovits_text_lang || '');
        setGptSovitsPromptLang(result.data.gpt_sovits_prompt_lang || '');
      } else {
        setLoadError(result.error || t('settings.perf.loadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl]);

  // 套用 perf 分頁的一鍵模式之後，這個分頁如果早就掛載著（Tabs.Content 預設
  // 不做 lazyMount），畫面顯示的引擎會停在套用前抓到的那份——跟 asr.tsx 同一個
  // 破綻、同一份任務簡報 Fix 1，見該檔案這段 effect 旁邊的完整說明。這裡照抄
  // 同一個修法：切回這個分頁時重新打一次 GET /api/perf，但只在 gpt_sovits 的
  // 兩個欄位「使用者還沒動過」（目前草稿仍等於上一次載入的伺服器值）時才用新
  // 值覆蓋，避免蓋掉使用者正在填的服務位址／參考音檔路徑。pendingEngine 完全
  // 不在這個 effect 的寫入範圍內，選了但還沒送出的 gpt_sovits_tts 草稿與待存
  // 提示都不受影響——提示裡的 currentEngineLabel 會因為 perf.tts_model 更新而
  // 跟著修正，同樣不需要為 pending notice 的過期問題另外寫機制。
  //
  // 讀取失敗時不設 loadError：這只是背景刷新，失敗了維持原本已經在畫面上、能
  // 動作的那份資料。
  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    (async () => {
      const result = await fetchPerf(baseUrl);
      if (cancelled || !result.ok) return;
      const data = result.data;
      setGptSovitsApiUrl((prev) => (
        perf && prev !== (perf.gpt_sovits_api_url || '')
          ? prev
          : (data.gpt_sovits_api_url || '')
      ));
      setGptSovitsRefAudioPath((prev) => (
        perf && prev !== (perf.gpt_sovits_ref_audio_path || '')
          ? prev
          : (data.gpt_sovits_ref_audio_path || '')
      ));
      setGptSovitsPromptText((prev) => (
        perf && prev !== (perf.gpt_sovits_prompt_text || '')
          ? prev
          : (data.gpt_sovits_prompt_text || '')
      ));
      setGptSovitsTextLang((prev) => (
        perf && prev !== (perf.gpt_sovits_text_lang || '')
          ? prev
          : (data.gpt_sovits_text_lang || '')
      ));
      setGptSovitsPromptLang((prev) => (
        perf && prev !== (perf.gpt_sovits_prompt_lang || '')
          ? prev
          : (data.gpt_sovits_prompt_lang || '')
      ));
      setPerf(data);
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, baseUrl]);

  const engineCollection = useMemo(() => createListCollection({
    items: (perf?.tts_models ?? []).map((name) => {
      const key = ttsModelLabelKey(name);
      return { label: key ? t(key) : name, value: name };
    }),
  }), [perf?.tts_models, t]);

  // text_lang／prompt_lang 共用同一份值域（後端 gpt_sovits_langs），文案卻要
  // 分開挑（見 gptSovitsLangLabelKey）——這裡只建一份 collection 給兩個
  // SelectField 共用，跟後端「同一份 single source of truth」的設計一致。
  const langCollection = useMemo(() => createListCollection({
    items: (perf?.gpt_sovits_langs ?? []).map((code) => {
      const key = gptSovitsLangLabelKey(code);
      return { label: key ? t(key) : code, value: code };
    }),
  }), [perf?.gpt_sovits_langs, t]);

  // 畫面上「選單顯示的引擎」：有未送出的草稿就顯示草稿，否則顯示 conf.yaml
  // 現在真正生效的引擎。gpt_sovits 欄位的顯示／隱藏也跟著這個值走，而不是
  // perf.tts_model——這樣選了 gpt_sovits_tts 之後欄位要立刻出現讓使用者
  // 輸入，不用等存檔成功才看得到。
  const displayedEngine = pendingEngine ?? perf?.tts_model ?? '';

  const currentEngineLabel = useMemo(() => {
    if (!perf) return '';
    const key = ttsModelLabelKey(perf.tts_model);
    return key ? t(key) : perf.tts_model;
  }, [perf, t]);

  // POST /api/perf/tts 的回應永遠是「現在的完整 tts 狀態」，不管這次送的是
  // 引擎還是 gpt_sovits 欄位——把它整份寫回 perf state 並同步輸入框，兩個
  // 存檔路徑（引擎切換／欄位儲存）都呼叫這個函式，不重複組裝欄位。
  const applySaveResult = useCallback((data: TtsSaveResult) => {
    setPerf((p) => (p ? {
      ...p,
      tts_model: data.tts_model,
      gpt_sovits_api_url: data.gpt_sovits_api_url,
      gpt_sovits_ref_audio_path: data.gpt_sovits_ref_audio_path,
      gpt_sovits_prompt_text: data.gpt_sovits_prompt_text,
      gpt_sovits_text_lang: data.gpt_sovits_text_lang,
      gpt_sovits_prompt_lang: data.gpt_sovits_prompt_lang,
    } : p));
    setGptSovitsApiUrl(data.gpt_sovits_api_url || '');
    setGptSovitsRefAudioPath(data.gpt_sovits_ref_audio_path || '');
    setGptSovitsPromptText(data.gpt_sovits_prompt_text || '');
    setGptSovitsTextLang(data.gpt_sovits_text_lang || '');
    setGptSovitsPromptLang(data.gpt_sovits_prompt_lang || '');
  }, []);

  // 下拉選單切換時：
  // - 選回目前已生效的引擎：沒有東西要存，只是清掉可能殘留的草稿。
  // - 選到 gpt_sovits_tts：不能立刻送出，理由見檔頭說明，先當成本機草稿。
  // - 選到 edge_tts：不需要任何欄位，切換當下就能真的動作，沿用即時存檔
  //   （跟 perf.tsx 的 keep_alive 模式、asr.tsx 的 sherpa_onnx 同一種模式）。
  const handleEngineChange = useCallback(async (value: string[]) => {
    const model = value[0];
    if (!model || !perf) return;

    if (model === perf.tts_model) {
      setPendingEngine(null);
      return;
    }

    if (model === NEEDS_CONFIG_ENGINE) {
      setPendingEngine(model);
      return;
    }

    setPendingEngine(null);
    setEngineSaving(true);
    const result = await setTtsModel(baseUrl, model);
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

  // gpt_sovits 欄位是文字輸入框，不做每個按鍵都送出——要有明確的「儲存」
  // 按鈕使用者才知道自己送出了什麼。
  //
  // 有 pendingEngine（使用者選了 gpt_sovits_tts 但還沒送出）時，這次連同
  // tts_model 一起送——這是唯一允許 conf.yaml 的 tts_model 被改成
  // gpt_sovits_tts 的路徑，確保送出去的當下引擎一定跟著兩個欄位，不會出現
  // 「引擎已切但欄位空著」的中間狀態。
  //
  // 沒有 pendingEngine（已經是目前生效的 gpt_sovits_tts，只是要更新欄位）
  // 時，只送 tts_model 以外的兩個欄位——不重複帶上已經相同的 tts_model。
  const handleSaveConfig = useCallback(async () => {
    if (!perf) return;
    const apiUrl = gptSovitsApiUrl.trim();
    const refAudioPath = gptSovitsRefAudioPath.trim();
    if (!apiUrl || !refAudioPath) return;

    const payload: {
      tts_model?: string
      gpt_sovits_api_url: string
      gpt_sovits_ref_audio_path: string
      gpt_sovits_prompt_text: string
      gpt_sovits_text_lang: string
      gpt_sovits_prompt_lang: string
    } = {
      gpt_sovits_api_url: apiUrl,
      gpt_sovits_ref_audio_path: refAudioPath,
      // prompt_text 允許空字串——見檔頭說明，這是唯一沒有必填閘門的欄位。
      gpt_sovits_prompt_text: gptSovitsPromptText.trim(),
      gpt_sovits_text_lang: gptSovitsTextLang,
      gpt_sovits_prompt_lang: gptSovitsPromptLang,
    };
    if (pendingEngine) payload.tts_model = pendingEngine;

    setSavingConfig(true);
    const result = await setTtsConfig(baseUrl, payload);
    setSavingConfig(false);
    if (result.ok) {
      applySaveResult(result.data);
      setPendingEngine(null);
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
  }, [
    baseUrl, perf, pendingEngine, gptSovitsApiUrl, gptSovitsRefAudioPath,
    gptSovitsPromptText, gptSovitsTextLang, gptSovitsPromptLang, applySaveResult, t,
  ]);

  // 「儲存」按鈕是否可按：兩個欄位都必須非空——這正是要防的事故本身：
  // 按下去只會把 tts_model 改成一個沒有可用設定的引擎（見 NEEDS_CONFIG_ENGINE
  // 上方的說明）。這裡沒有 asr.tsx 那種「舊憑證仍留在 conf.yaml 裡就視為
  // 已有來源」的判斷——這兩個欄位不是憑證，永遠明碼顯示在輸入框裡，
  // 「欄位是否非空」直接等於「送出去的當下設定是否完整」。
  const hasApiUrl = Boolean(gptSovitsApiUrl.trim());
  const hasRefAudioPath = Boolean(gptSovitsRefAudioPath.trim());

  // 沒有 pendingEngine 時（已經是目前生效的 gpt_sovits_tts），額外擋下
  // 「所有欄位都跟 conf.yaml 現值一樣、什麼都沒異動」的無意義送出——不讓
  // 使用者誤按到一個什麼都沒變的儲存。有 pendingEngine 時不做這個判斷：
  // 引擎本身就是要送出的變更。五個欄位都要比對，只比 api_url／ref_audio_path
  // 兩個的話，使用者只改了 prompt_text 或語言選單、按下儲存會被誤判成
  // 「沒變」而擋下——那正是這裡要防的事故本身。
  const configUnchanged = Boolean(
    perf
    && !pendingEngine
    && perf.tts_model === NEEDS_CONFIG_ENGINE
    && gptSovitsApiUrl.trim() === (perf.gpt_sovits_api_url || '').trim()
    && gptSovitsRefAudioPath.trim() === (perf.gpt_sovits_ref_audio_path || '').trim()
    && gptSovitsPromptText.trim() === (perf.gpt_sovits_prompt_text || '').trim()
    && gptSovitsTextLang === (perf.gpt_sovits_text_lang || '')
    && gptSovitsPromptLang === (perf.gpt_sovits_prompt_lang || ''),
  );
  const configSaveDisabled = !hasApiUrl || !hasRefAudioPath || configUnchanged;

  // 只有在「目前這個角色真的釘了引擎」時才警告。常駐的免責聲明會被當成背景
  // 雜訊，看到跟沒看到一樣；只有指名道姓才會被讀進去。
  const characterOverride = perf?.engine_overrides_by_character?.[confName]?.tts_model
    || null;

  // 一鍵裝好之後，後端已經把引擎切到 GPT-SoVITS。重新讀一次，讓選單和欄位跟上。
  const handleVoiceInstalled = useCallback(async () => {
    const result = await fetchPerf(baseUrl);
    if (!result.ok) return;
    setPendingEngine(null);
    applySaveResult({ ...result.data, restart_required: false });
  }, [baseUrl, applySaveResult]);

  return (
    <Stack {...settingStyles.common.container} gap={2}>
      <Heading size="sm">{t('settings.perf.ttsSectionTitle')}</Heading>
      {/* 常駐提示（不是 toast）：這個分頁自己存檔，不受外層抽屜 Save/Cancel
          影響——使用者需要隨時能看到「這格歸誰管」，跟 asr.tsx 的
          asrEngineSectionNote 同一個理由。 */}
      <Text fontSize="xs" color="blue.300">{t('settings.perf.ttsEngineSectionNote')}</Text>
      {/* 角色檔自己的 tts_config 會蓋掉這裡選的引擎（見 api/perf.ts 的
          engine_overrides_by_character 註解）。沒有這行警告的時候，使用者在
          這裡選了 GPT-SoVITS、存檔成功、卻一直聽到內建的聲音，畫面上找不到
          任何線索——所以在他們動手之前就先說。 */}
      {characterOverride && (
        <Text fontSize="xs" color="orange.300">
          {t('settings.perf.ttsCharacterOverride', {
            character: confName,
            engine: characterOverride,
          })}
        </Text>
      )}
      <Text fontSize="xs" color="whiteAlpha.600">{t('settings.perf.ttsEngineHelp')}</Text>

      {/* 還沒裝 GPT-SoVITS 的人在這裡也能一鍵裝：精靈裡跳過的人不必自己找教學。 */}
      <GptSovitsInstall baseUrl={baseUrl} onInstalled={handleVoiceInstalled} />

      {loadError && (
        <Text fontSize="sm" color="red.300">{loadError}</Text>
      )}

      {!loadError && !perf && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.perf.loading')}</Text>
      )}

      {perf && (
        <>
          <SelectField
            label={t('settings.perf.ttsEngineLabel')}
            value={displayedEngine ? [displayedEngine] : []}
            onChange={handleEngineChange}
            collection={engineCollection}
            placeholder={t('settings.perf.ttsEnginePlaceholder')}
          />
          {engineSaving && (
            <Text fontSize="xs" color="whiteAlpha.600">{t('settings.perf.applying')}</Text>
          )}
          {/* 常駐提示：選了 gpt_sovits_tts 但還沒按下面的儲存——畫面上的
              選擇跟 conf.yaml 現在真正生效的引擎不一樣，這件事必須隨時
              可見，不能只靠使用者自己記得。 */}
          {pendingEngine && (
            <Text fontSize="xs" color="orange.300">
              {t('settings.perf.ttsEnginePendingNotice', { current: currentEngineLabel })}
            </Text>
          )}

          {/* gpt_sovits_tts 需要兩個欄位才能真正動作——依畫面上選到的引擎
              （displayedEngine，可能還只是草稿）顯示對應欄位。 */}
          {displayedEngine === NEEDS_CONFIG_ENGINE && (
            <Stack gap={2}>
              <InputField
                label={t('settings.perf.gptSovitsApiUrlLabel')}
                value={gptSovitsApiUrl}
                onChange={setGptSovitsApiUrl}
                help={t('settings.perf.gptSovitsApiUrlHelp')}
              />
              <InputField
                label={t('settings.perf.gptSovitsRefAudioLabel')}
                value={gptSovitsRefAudioPath}
                onChange={setGptSovitsRefAudioPath}
                help={t('settings.perf.gptSovitsRefAudioHelp')}
              />
              {/* prompt_text：參考音檔的逐字稿，唯一的可選欄位——不擋存檔，
                  只用 help tooltip 講清楚留空的代價，見檔頭說明。 */}
              <InputField
                label={t('settings.perf.gptSovitsPromptTextLabel')}
                value={gptSovitsPromptText}
                onChange={setGptSovitsPromptText}
                help={t('settings.perf.gptSovitsPromptTextHelp')}
              />
              <SelectField
                label={t('settings.perf.gptSovitsTextLangLabel')}
                value={gptSovitsTextLang ? [gptSovitsTextLang] : []}
                onChange={(value) => setGptSovitsTextLang(value[0] || '')}
                collection={langCollection}
                placeholder={t('settings.perf.gptSovitsLangPlaceholder')}
                help={t('settings.perf.gptSovitsTextLangHelp')}
              />
              <SelectField
                label={t('settings.perf.gptSovitsPromptLangLabel')}
                value={gptSovitsPromptLang ? [gptSovitsPromptLang] : []}
                onChange={(value) => setGptSovitsPromptLang(value[0] || '')}
                collection={langCollection}
                placeholder={t('settings.perf.gptSovitsLangPlaceholder')}
                help={t('settings.perf.gptSovitsPromptLangHelp')}
              />
              {/* 常駐提示，不是等使用者按下去才跳錯誤：缺任一欄位時儲存
                  按鈕會被擋下（見 configSaveDisabled），沒有這行文字的話，
                  使用者只會看到一顆按不下去的按鈕、猜不到少填了什麼。 */}
              {(!hasApiUrl || !hasRefAudioPath) && (
                <Text fontSize="xs" color="orange.300">
                  {t('settings.perf.gptSovitsFieldsRequired')}
                </Text>
              )}
              {/* 缺必填欄位有解釋，「沒有變更」卻沒有——那顆按鈕一樣是暗的，
                  使用者一樣按不下去，卻看不到任何原因。這是「怎麼儲存不了」
                  真正的來源：欄位都填好了，所以上面那行提示不會出現。 */}
              {hasApiUrl && hasRefAudioPath && configUnchanged && (
                <Text fontSize="xs" color="whiteAlpha.600">
                  {t('settings.perf.ttsConfigUnchanged')}
                </Text>
              )}
              <Button
                size="xs"
                tone="blue"
                onClick={handleSaveConfig}
                loading={savingConfig}
                disabled={configSaveDisabled}
                className="self-start"
              >
                {t('common.save')}
              </Button>
            </Stack>
          )}
        </>
      )}
    </Stack>
  );
}

export default TTS;
