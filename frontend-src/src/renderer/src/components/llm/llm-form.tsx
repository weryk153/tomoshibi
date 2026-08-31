/* eslint-disable import/no-extraneous-dependencies */
// 共用的 LLM 設定表單：apikey／ollama／custom 三種模式共用一個 Test & Save。
// Task 4 把這個元件掛進設定分頁，Task 5 把它包成首次精靈的全螢幕畫面——表單
// 狀態、載入現值、送出與錯誤顯示都在這裡自己管，呼叫端只需要知道存檔成功了
// （見 onSaved）。

import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import {
  Stack, Text, Tabs, Box, HStack,
} from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { useWebSocket } from '@/context/websocket-context';
import { InputField, SelectField } from '../sidebar/setting/common';
import { settingStyles } from '../sidebar/setting/setting-styles';
import {
  fetchLlmConfig,
  saveLlmConfig,
  fetchOllamaModels,
  detectModels,
  applyDetectedModel,
  pullOllamaModel,
  type LlmMode,
  type ApiKeyProvider,
  type LlmFormState,
  type LlmSaveResult,
  type DetectResponse,
  type DetectedModel,
  type OllamaPullEvent,
} from '@/api/llm-config.ts';

interface LlmFormProps {
  onSaved: (result: LlmSaveResult) => void
}

// 純顯示用的範例模型名稱——只是給使用者一個參考（modelHelp 的 {{example}}
// 插值），留空時不會被偷偷代入送出的 payload。Task 2 的 buildSavePayload 刻意
// 不做欄位驗證或預設值替換：留白直接送出，讓後端「Missing model name.」這種
// 人類可讀的錯誤訊息帶使用者修正，前端另維護一份規則只會跟後端漂移。
const PROVIDER_MODEL_EXAMPLE: Record<ApiKeyProvider, string> = {
  openai: 'gpt-4o-mini',
  claude: 'claude-3-5-haiku-20241022',
  gemini: 'gemini-1.5-flash',
};

// 品牌名稱，不走 i18n——跟程式碼裡其他專有名詞（Ollama、conf.yaml）一致。
const PROVIDER_LABELS: Record<ApiKeyProvider, string> = {
  openai: 'OpenAI',
  claude: 'Claude',
  gemini: 'Gemini',
};

interface OllamaModelsResponse {
  available?: boolean
  models?: string[]
}

type OllamaProbeStatus = 'idle' | 'loading' | 'unavailable' | 'empty' | 'ready';

// 金鑰欄位留空、但後端已經存有一把金鑰時，使用者可能以為「留空 = 沿用舊金鑰」
// ——設定裡其他遮罩欄位（例如 groq/azure 的 API key）確實是這樣運作的。但這裡
// api_key_masked 只是遮罩字串（例如 "sk-x****"），前端拿不到明文可以重送，
// 後端存檔又要求 api_key 非空，所以「沿用」技術上做不到：必須擋下送出，
// 請使用者重新貼上一次。文案走 t('setup.keyRequiredAgain')／
// t('setup.keyAlreadySetPlaceholder')——五語言都已補齊，見 locales/*/translation.json。

// 左邊一條色條 + 一句話的提示框。原本只給「思考模式」那句警告用（叫
// ReasoningModelWarning），偵測流程套用成功後要顯示 note（例如「已為你關閉
// 思考模式：不關會超過 60 秒 timeout」）——語意跟措辭都跟原本那句警告是同一
// 類東西，所以擴充成通用元件、加一個 tone，而不是另外複製一份幾乎一樣的框。
function NoticeBox({ text, tone = 'yellow' }: { text: string; tone?: 'yellow' | 'blue' }): JSX.Element {
  const borderColor = tone === 'yellow' ? 'yellow.400' : 'blue.400';
  const textColor = tone === 'yellow' ? 'yellow.200' : 'blue.200';
  return (
    <Box
      borderLeft="3px solid"
      borderColor={borderColor}
      bg="whiteAlpha.100"
      px={3}
      py={2}
      borderRadius="sm"
    >
      <Text fontSize="xs" color={textColor}>
        {text}
      </Text>
    </Box>
  );
}

function LlmForm({ onSaved }: LlmFormProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl: backendBaseUrl } = useWebSocket();

  const [mode, setMode] = useState<LlmMode>('apikey');
  const [provider, setProvider] = useState<ApiKeyProvider>('openai');
  const [apiKey, setApiKey] = useState('');
  const [model, setModel] = useState('');
  const [customUrl, setCustomUrl] = useState('');

  // 掛載時 fetchLlmConfig 回來後才知道是否已經有金鑰；在那之前不允許送出，
  // 否則「留空 = 已配置，要擋下」的判斷會用到還沒載入完成的預設值 false。
  const [hasExistingKey, setHasExistingKey] = useState(false);
  const [isLoadingInitial, setIsLoadingInitial] = useState(true);

  const [ollamaStatus, setOllamaStatus] = useState<OllamaProbeStatus>('idle');
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // 掛載時載入現值。api_key_masked 絕對不填進金鑰欄位——那是遮罩字串，送回去
  // 會把真正的金鑰存成一串垃圾。「是否已有金鑰」用 has_real_key 判斷，不能用
  // api_key_masked 是否非空：佔位金鑰（例如 'your api key here'）遮罩後也是
  // 非空字串，但精靈只在金鑰是佔位符時才會出現——用遮罩字串推斷會讓每個第一次
  // 使用的人都被告知「已經存過金鑰」，has_real_key 是後端算好的真值。
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchLlmConfig(backendBaseUrl);
      if (cancelled) return;
      if (result.ok) {
        setModel(result.data.model || '');
        setCustomUrl(result.data.base_url || '');
        setHasExistingKey(Boolean(result.data.has_real_key));
      }
      setIsLoadingInitial(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [backendBaseUrl]);

  const probeOllama = useCallback(async () => {
    setOllamaStatus('loading');
    const result = await fetchOllamaModels(backendBaseUrl);
    if (!result.ok) {
      setOllamaStatus('unavailable');
      setOllamaModels([]);
      return;
    }
    const data = result.data as OllamaModelsResponse;
    if (!data.available) {
      setOllamaStatus('unavailable');
      setOllamaModels([]);
      return;
    }
    const models = Array.isArray(data.models) ? data.models : [];
    if (models.length === 0) {
      setOllamaStatus('empty');
      setOllamaModels([]);
      return;
    }
    setOllamaStatus('ready');
    setOllamaModels(models);
  }, [backendBaseUrl]);

  // 切到 ollama 分頁時自動探測一次；之後靠 Refresh 按鈕手動重試，
  // 不要每次重新渲染都打一次 /ollama-models。
  useEffect(() => {
    if (mode === 'ollama' && ollamaStatus === 'idle') {
      probeOllama();
    }
  }, [mode, ollamaStatus, probeOllama]);

  // --- 偵測本機模型（Task 8 的兩個端點） ------------------------------------ //
  //
  // 跟上面的 ollama 分頁探測是兩條獨立的路：這裡一開表單就自動掃，掃的是
  // LM Studio ＋ Ollama 兩個推論端而不是只有 Ollama，找到的話可以直接選、
  // 直接套用（含必要設定），不必先選分頁、填欄位。手動填表的路徑完全不動
  // ——這條只是加速，掃不到東西或掃失敗都不擋住下面的表單。
  type DetectStatus = 'loading' | 'ready' | 'error';
  const [detectStatus, setDetectStatus] = useState<DetectStatus>('loading');
  const [detectResult, setDetectResult] = useState<DetectResponse | null>(null);
  const [detectError, setDetectError] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);

  type ApplyPhase = 'idle' | 'applying' | 'applied' | 'error';
  const [applyPhase, setApplyPhase] = useState<ApplyPhase>('idle');
  const [applyError, setApplyError] = useState<string | null>(null);
  const [appliedInfo, setAppliedInfo] = useState<{
    model: string
    baseUrl: string
    note: string | null
  } | null>(null);

  type PullPhase = 'idle' | 'preparing' | 'downloading' | 'error';
  const [pullPhase, setPullPhase] = useState<PullPhase>('idle');
  const [pullPercent, setPullPercent] = useState<number | null>(null);
  const [pullError, setPullError] = useState<string | null>(null);

  // /api/llm-config/detect 的 ollama_available／lmstudio_available 其實是
  // 「探測到至少一顆模型」（route 裡就是 bool(lms)／bool(olm)，兩份清單都是
  // 探測不到東西時一律回空陣列），不是「daemon 有沒有在跑」。這代表「Ollama
  // 在跑但沒有模型」跟「Ollama 根本沒裝」在這個端點的回應裡是同一個值
  // （false + 空清單），單靠它分不出來——brief 的四狀態表格假設這兩種狀態
  // 分得出來，但拿到的資料做不到。
  //
  // Ollama 這邊有補救：既有的 /api/llm-config/ollama-models（這裡就是
  // fetchOllamaModels，Ollama 分頁探測在用的那支）回的 available 是真正的
  // 「連得到 daemon」，跟模型數量無關，所以清單是空的時候額外打一次，用它
  // 分辨「在跑但沒模型」與「沒在跑」。LM Studio 沒有對應的端點，這個區分目前
  // 做不到——下面 lmstudio-empty 那個分支因此永遠不會被觸發，是刻意保留、
  // 有註解的死路，不是漏刪：detect 端點未來若把 lmstudio_available 改成真正
  // 的可達性訊號，這裡不用再改就會生效。詳情見這次任務的報告。
  const [ollamaReachable, setOllamaReachable] = useState<boolean | null>(null);

  const runDetect = useCallback(async () => {
    setDetectStatus('loading');
    setDetectError(null);
    setOllamaReachable(null);
    const result = await detectModels(backendBaseUrl);
    if (!result.ok) {
      setDetectStatus('error');
      setDetectError(result.error);
      return;
    }
    setDetectResult(result.data);

    if (result.data.models.length === 0) {
      const probe = await fetchOllamaModels(backendBaseUrl);
      const reachable = probe.ok && Boolean((probe.data as { available?: boolean } | null)?.available);
      setOllamaReachable(reachable);
    }
    setDetectStatus('ready');
  }, [backendBaseUrl]);

  // 掛載時掃一次。跟 fetchLlmConfig 那個效果不同，這裡不用 cancelled guard——
  // 掃描失敗只是顯示一句錯誤，不像 hasExistingKey 那樣會影響送出邏輯的正確性。
  useEffect(() => {
    runDetect();
  }, [runDetect]);

  // id 只在各自的 backend 底下保證唯一，LM Studio 跟 Ollama 剛好都在跑、
  // 剛好都有一顆同名模型時，光用 id 當 key／當選取依據會兩顆一起選中。
  const detectModelKey = (m: DetectedModel): string => `${m.backend}:${m.id}`;

  const handleSelectDetected = useCallback((m: DetectedModel) => {
    setSelectedKey(detectModelKey(m));
    setApplyPhase('idle');
    setApplyError(null);
  }, []);

  const handleApplyDetected = useCallback(async () => {
    if (!detectResult || !selectedKey) return;
    const chosen = detectResult.models.find((m) => detectModelKey(m) === selectedKey);
    if (!chosen) return;

    setApplyPhase('applying');
    setApplyError(null);
    const result = await applyDetectedModel(backendBaseUrl, chosen.backend, chosen.id);

    if (!result.ok) {
      setApplyPhase('error');
      setApplyError(result.error);
      return;
    }
    if (!result.data.ok || !result.data.applied) {
      setApplyPhase('error');
      setApplyError(result.data.error || t('setup.testFailed'));
      return;
    }

    setAppliedInfo({
      model: result.data.applied.model,
      baseUrl: chosen.base_url,
      note: result.data.note ?? null,
    });
    setApplyPhase('applied');
  }, [detectResult, selectedKey, backendBaseUrl, t]);

  // 套用成功後不直接呼叫 onSaved：在首次精靈裡，onSaved 一叫外層就把整個
  // LlmForm 換成「已完成」畫面，note（例如「已為你關閉思考模式」）會連顯示
  // 的機會都沒有就消失。改成先在這裡把 note 顯示出來，使用者按下「開始聊天」
  // 才真正呼叫 onSaved 收尾——跟 first-run-wizard 原本「顯示結果→按按鈕關閉」
  // 的兩段式是同一個模式。
  const handleContinueAfterApply = useCallback(() => {
    if (!appliedInfo) return;
    onSaved({
      ok: true,
      model: appliedInfo.model,
      base_url: appliedInfo.baseUrl,
      api_key_masked: '',
      restart_required: true,
    });
  }, [appliedInfo, onSaved]);

  const handlePullRecommended = useCallback(async () => {
    if (!detectResult) return;
    const modelName = detectResult.recommended_pull;
    setPullPhase('preparing');
    setPullError(null);
    setPullPercent(null);

    const result = await pullOllamaModel(backendBaseUrl, modelName, (event: OllamaPullEvent) => {
      if (typeof event.completed === 'number' && typeof event.total === 'number' && event.total > 0) {
        setPullPhase('downloading');
        setPullPercent(Math.round((event.completed / event.total) * 100));
      } else if (event.status && event.status !== 'error') {
        setPullPhase((prev) => (prev === 'idle' ? 'preparing' : prev));
      }
    });

    if (!result.ok) {
      setPullPhase('error');
      // 訊息在這裡組完整句，畫面上直接顯示 pullError，不要在 render 端二次包裝
      // ——不然 result.error 缺席時的 generic 訊息會被 ollamaDownloadFailed 的
      // {{error}} 佔位符再包一層，變成語意重複的句子。
      setPullError(
        result.error
          ? t('setup.ollamaDownloadFailed', { error: result.error })
          : t('setup.ollamaDownloadFailedGeneric'),
      );
      return;
    }
    // 下載完成：重新掃一次，讓剛下載的模型出現在清單裡可以選。
    setPullPhase('idle');
    setPullPercent(null);
    await runDetect();
  }, [detectResult, backendBaseUrl, runDetect, t]);

  const providerCollection = useMemo(
    // 明確標注泛型為 { label: string; value: string }——SelectField 的 collection
    // prop 就是這個型別。若讓它從 ApiKeyProvider[] 推論，value 會被推成
    // ApiKeyProvider 這個更窄的聯集型別，跟 SelectFieldProps 對不上會炸在編譯期。
    () => createListCollection<{ label: string; value: string }>({
      items: (Object.keys(PROVIDER_LABELS) as ApiKeyProvider[]).map((value) => ({
        label: PROVIDER_LABELS[value],
        value,
      })),
    }),
    [],
  );

  const ollamaCollection = useMemo(
    () => createListCollection({
      items: ollamaModels.map((name) => ({ label: name, value: name })),
    }),
    [ollamaModels],
  );

  const handleSubmit = useCallback(async () => {
    setSaveError(null);

    if ((mode === 'apikey' || mode === 'custom') && apiKey.trim() === '' && hasExistingKey) {
      setSaveError(t('setup.keyRequiredAgain'));
      return;
    }

    const state: LlmFormState = {
      mode,
      provider,
      apiKey,
      model,
      baseUrl: customUrl,
    };

    setIsSaving(true);
    const result = await saveLlmConfig(backendBaseUrl, state);
    setIsSaving(false);

    if (result.ok) {
      onSaved(result.data);
      return;
    }
    // 後端的錯誤訊息已去除金鑰且是人類可讀的（例如 "Missing API key."），
    // 直接顯示比翻成通用的 testFailed 更有用；只有 error 為空時才退回它。
    setSaveError(result.error || t('setup.testFailed'));
  }, [mode, provider, apiKey, model, customUrl, hasExistingKey, backendBaseUrl, onSaved, t]);

  const existingKeyPlaceholder = hasExistingKey ? t('setup.keyAlreadySetPlaceholder') : undefined;

  return (
    <Stack {...settingStyles.common.container}>
      <Stack gap={3}>
        <Text fontWeight="bold">{t('setup.detectTitle')}</Text>

        {applyPhase === 'applied' && appliedInfo ? (
          <Stack gap={3}>
            <Text fontWeight="semibold" color="green.300">
              {t('setup.detectApplied', { model: appliedInfo.model })}
            </Text>
            {appliedInfo.note && <NoticeBox text={appliedInfo.note} tone="blue" />}
            <Text fontSize="sm" color="whiteAlpha.700">
              {t('setup.savedRestart')}
            </Text>
            <Button tone="blue" onClick={handleContinueAfterApply} className="self-start">
              {t('setup.startChatting')}
            </Button>
          </Stack>
        ) : (
          <Stack gap={3}>
            {detectStatus === 'loading' && (
              <Text fontSize="sm" color="whiteAlpha.700">
                {t('setup.detectScanning')}
              </Text>
            )}

            {detectStatus === 'error' && detectError && (
              <Text fontSize="sm" color="red.300">{detectError}</Text>
            )}

            {detectStatus === 'ready' && detectResult && detectResult.models.length > 0 && (
              <Stack gap={2}>
                <Text fontSize="sm" color="whiteAlpha.700">{t('setup.detectFound')}</Text>
                <Stack gap={2}>
                  {detectResult.models.map((m) => {
                    const key = detectModelKey(m);
                    const selected = key === selectedKey;
                    return (
                      <Box
                        key={key}
                        onClick={() => handleSelectDetected(m)}
                        cursor="pointer"
                        borderWidth="1px"
                        borderColor={selected ? 'blue.400' : 'whiteAlpha.200'}
                        bg={selected ? 'blue.900' : 'whiteAlpha.50'}
                        borderRadius="md"
                        px={3}
                        py={2}
                      >
                        <Text fontWeight="semibold">{m.id}</Text>
                        <HStack flexWrap="wrap" gap={2} mt={1}>
                          <Text fontSize="xs" color="whiteAlpha.600">{m.backend}</Text>
                          {m.is_vlm && (
                            <Text fontSize="xs" color="purple.300">{t('setup.detectVision')}</Text>
                          )}
                          {m.supports_tools && (
                            <Text fontSize="xs" color="teal.300">{t('setup.detectTools')}</Text>
                          )}
                        </HStack>
                      </Box>
                    );
                  })}
                </Stack>
                <Button
                  tone="blue"
                  onClick={handleApplyDetected}
                  loading={applyPhase === 'applying'}
                  disabled={!selectedKey || applyPhase === 'applying'}
                  className="self-start"
                >
                  {t('setup.detectUse')}
                </Button>
                {applyPhase === 'error' && applyError && (
                  <Text fontSize="sm" color="red.300">{applyError}</Text>
                )}
              </Stack>
            )}

            {detectStatus === 'ready' && detectResult && detectResult.models.length === 0
              && ollamaReachable === true && (
                <Stack gap={2}>
                  <Text fontSize="sm" color="orange.300">{t('setup.detectEmptyOllama')}</Text>
                  <Text fontWeight="semibold">{t('setup.ollamaRecommendedTitle')}</Text>
                  <Text fontSize="sm" color="whiteAlpha.700">
                    {t('setup.ollamaRecommendedDesc', { model: detectResult.recommended_pull })}
                  </Text>

                  {pullPhase === 'idle' && (
                    <Button tone="blue" onClick={handlePullRecommended} className="self-start">
                      {t('setup.ollamaUseRecommended', { model: detectResult.recommended_pull })}
                    </Button>
                  )}
                  {pullPhase === 'preparing' && (
                    <Text fontSize="sm" color="whiteAlpha.700">
                      {t('setup.ollamaDownloadPreparing')}
                    </Text>
                  )}
                  {pullPhase === 'downloading' && (
                    <Text fontSize="sm" color="whiteAlpha.700">
                      {t('setup.ollamaDownloading', { percent: pullPercent ?? 0 })}
                    </Text>
                  )}
                  {pullPhase === 'error' && pullError && (
                    <Text fontSize="sm" color="red.300">{pullError}</Text>
                  )}
                </Stack>
            )}

            {/* 目前永遠不會觸發：detect 端點的 lmstudio_available 是「探測到
                模型」而不是「daemon 可達」，兩者都空清單時無法區分「LM Studio
                在跑但沒模型」與「根本沒裝」。沒有對應 ollama-models 那種的
                獨立探測端點可用，這個區分做不到——見上面 ollamaReachable
                旁邊的說明與這次任務報告。分支留著：一旦 detect 端點修好，
                這裡不用改就會生效。 */}
            {detectStatus === 'ready' && detectResult && detectResult.models.length === 0
              && ollamaReachable === false && detectResult.lmstudio_available && (
                <Text fontSize="sm" color="orange.300">{t('setup.detectEmptyLmStudio')}</Text>
            )}

            {detectStatus === 'ready' && detectResult && detectResult.models.length === 0
              && ollamaReachable === false && !detectResult.lmstudio_available && (
                <Text fontSize="sm" color="orange.300">{t('setup.detectNothingRunning')}</Text>
            )}
          </Stack>
        )}
      </Stack>

      <Tabs.Root
        value={mode}
        onValueChange={(details) => setMode(details.value as LlmMode)}
        {...settingStyles.settingUI.tabs.root}
      >
        <Tabs.List {...settingStyles.settingUI.tabs.list}>
          <Tabs.Trigger value="apikey" {...settingStyles.settingUI.tabs.trigger}>
            {t('setup.tabApiKey')}
          </Tabs.Trigger>
          <Tabs.Trigger value="ollama" {...settingStyles.settingUI.tabs.trigger}>
            {t('setup.tabOllama')}
          </Tabs.Trigger>
          <Tabs.Trigger value="custom" {...settingStyles.settingUI.tabs.trigger}>
            {t('setup.tabCustom')}
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="apikey" {...settingStyles.settingUI.tabs.content}>
          <Stack gap={6}>
            <SelectField
              label={t('setup.providerLabel')}
              value={[provider]}
              onChange={(value) => {
                if (value[0]) setProvider(value[0] as ApiKeyProvider);
              }}
              collection={providerCollection}
              placeholder={t('setup.providerLabel')}
            />

            <InputField
              label={t('setup.apiKeyLabel')}
              value={apiKey}
              onChange={setApiKey}
              type="password"
              placeholder={existingKeyPlaceholder}
              help={t('setup.apiKeyHelp')}
            />

            <InputField
              label={t('setup.modelLabel')}
              value={model}
              onChange={setModel}
              placeholder={PROVIDER_MODEL_EXAMPLE[provider]}
              help={t('setup.modelHelp', { example: PROVIDER_MODEL_EXAMPLE[provider] })}
            />

            <NoticeBox text={t('setup.reasoningModelWarning')} />
          </Stack>
        </Tabs.Content>

        <Tabs.Content value="ollama" {...settingStyles.settingUI.tabs.content}>
          <Stack gap={6}>
            <Text fontSize="sm" color="whiteAlpha.700">
              {t('setup.ollamaIntro')}
            </Text>

            <Text {...settingStyles.general.fieldLabel} fontWeight="semibold">
              {t('setup.ollamaModelLabel')}
            </Text>

            {ollamaStatus === 'loading' && (
              <Text fontSize="sm" color="whiteAlpha.700">
                {t('setup.ollamaProbing')}
              </Text>
            )}

            {ollamaStatus === 'ready' && (
              <SelectField
                label={t('setup.ollamaQuickPick')}
                value={model ? [model] : []}
                onChange={(value) => setModel(value[0] ?? '')}
                collection={ollamaCollection}
                placeholder={t('setup.ollamaQuickPickPlaceholder')}
              />
            )}

            {(ollamaStatus === 'unavailable' || ollamaStatus === 'empty') && (
              <>
                <Text fontSize="sm" color="orange.300">
                  {ollamaStatus === 'unavailable'
                    ? t('setup.ollamaUnavailable')
                    : t('setup.ollamaNoModels')}
                </Text>
                <InputField
                  label={t('setup.ollamaModelManualLabel')}
                  value={model}
                  onChange={setModel}
                  help={t('setup.ollamaModelManualHelp')}
                />
              </>
            )}

            <Button
              size="sm"
              variant="outline"
              onClick={probeOllama}
              loading={ollamaStatus === 'loading'}
              className="self-start"
            >
              {t('setup.ollamaRefresh')}
            </Button>
          </Stack>
        </Tabs.Content>

        <Tabs.Content value="custom" {...settingStyles.settingUI.tabs.content}>
          <Stack gap={6}>
            <Text fontSize="sm" color="whiteAlpha.700">
              {t('setup.customIntro')}
            </Text>

            <InputField
              label={t('setup.customBaseUrlLabel')}
              value={customUrl}
              onChange={setCustomUrl}
            />

            <InputField
              label={t('setup.customModelLabel')}
              value={model}
              onChange={setModel}
            />

            <InputField
              label={t('setup.customKeyLabel')}
              value={apiKey}
              onChange={setApiKey}
              type="password"
              placeholder={existingKeyPlaceholder}
              help={t('setup.customKeyHelp')}
            />

            <NoticeBox text={t('setup.reasoningModelWarning')} />
          </Stack>
        </Tabs.Content>
      </Tabs.Root>

      {saveError && (
        <Text fontSize="sm" color="red.300">
          {saveError}
        </Text>
      )}

      <Button
        tone="blue"
        onClick={handleSubmit}
        loading={isSaving}
        loadingText={t('setup.testing')}
        // 明講 isSaving 才是「這顆按鈕在存檔中必須擋住重複送出」的實際保證。
        // 目前 Button 包裝元件內部用 disabled={loading || disabled} 也會擋，
        // 但那是另一個元件的實作細節——它日後若改掉，這裡不該跟著悄悄失效。
        disabled={isLoadingInitial || isSaving}
      >
        {t('setup.testAndSave')}
      </Button>
    </Stack>
  );
}

export default LlmForm;
