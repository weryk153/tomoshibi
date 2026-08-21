/* eslint-disable import/no-extraneous-dependencies */
// 共用的 LLM 設定表單：apikey／ollama／custom 三種模式共用一個 Test & Save。
// Task 4 把這個元件掛進設定分頁，Task 5 把它包成首次精靈的全螢幕畫面——表單
// 狀態、載入現值、送出與錯誤顯示都在這裡自己管，呼叫端只需要知道存檔成功了
// （見 onSaved）。

import {
  useCallback, useEffect, useMemo, useState,
} from 'react';
import { Stack, Text, Tabs, Box } from '@chakra-ui/react';
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
  type LlmMode,
  type ApiKeyProvider,
  type LlmFormState,
  type LlmSaveResult,
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

function ReasoningModelWarning({ text }: { text: string }): JSX.Element {
  return (
    <Box
      borderLeft="3px solid"
      borderColor="yellow.400"
      bg="whiteAlpha.100"
      px={3}
      py={2}
      borderRadius="sm"
    >
      <Text fontSize="xs" color="yellow.200">
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

            <ReasoningModelWarning text={t('setup.reasoningModelWarning')} />
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

            <ReasoningModelWarning text={t('setup.reasoningModelWarning')} />
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
