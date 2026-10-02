// 模型頁的「背景工作與工具」：網路搜尋工具開關、背景工作另外用的模型。從原本
// 的「一般」分頁搬來。改了就存到 conf.yaml；要重新載入才生效，由抽屜頂端的
// 提示處理。
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Stack, Text } from '@chakra-ui/react';
import { useWebSocket } from '@/context/websocket-context';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import {
  fetchUseMcpp, setUseMcpp, fetchEngineSettings, saveEngineSettings,
  type EngineSettings,
} from '@/api/agent-config.ts';
import { SwitchField, InputField } from './common';

function ModelExtras(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();

  // 工具開關：存失敗就退回原值，不留一個「畫面上開著、conf.yaml 其實沒存到」的假象。
  const [mcpEnabled, setMcpEnabled] = useState(false);
  const [mcpLoading, setMcpLoading] = useState(true);
  const [mcpLoadError, setMcpLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchUseMcpp(baseUrl);
      if (cancelled) return;
      setMcpLoading(false);
      if (result.ok) {
        setMcpEnabled(result.data);
      } else {
        setMcpLoadError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  const mcpSaver = useAutosave(async (checked: boolean) => {
    const result = await setUseMcpp(baseUrl, checked);
    if (result.ok) {
      setMcpEnabled(result.data.use_mcpp);
      return { ok: true } as const;
    }
    setMcpEnabled(!checked);
    return { ok: false, error: result.error } as const;
  }, { delayMs: 0 });

  // 背景工作另外用的模型：兩欄一起存，填一半的話後端不會用。
  const [engine, setEngine] = useState<EngineSettings | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [backgroundDraft, setBackgroundDraft] = useState<{ url: string; model: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchEngineSettings(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setEngine(result.data);
        setBackgroundDraft({
          url: result.data.background_base_url,
          model: result.data.background_model,
        });
      } else {
        setEngineError(result.error);
      }
    })();
    return (): void => {
      cancelled = true;
    };
  }, [baseUrl]);

  const backgroundSaver = useAutosave(async (draft: { url: string; model: string }) => {
    const url = draft.url.trim();
    const model = draft.model.trim();
    const result = await saveEngineSettings(baseUrl, {
      background_base_url: url,
      background_model: model,
    });
    if (!result.ok) return { ok: false, error: result.error } as const;
    setEngine((current) => (current ? { ...current, ...result.data } : current));
    // 後端不寫它認為會弄壞設定檔的值（不是 http 網址、含引號或換行）。
    if (result.data.background_base_url !== url || result.data.background_model !== model) {
      return { ok: false, error: t('settings.general.engineBackgroundInvalid') } as const;
    }
    return { ok: true } as const;
  });

  const changeBackground = (field: 'url' | 'model', value: string): void => {
    if (!backgroundDraft) return;
    const next = { ...backgroundDraft, [field]: value };
    setBackgroundDraft(next);
    backgroundSaver.change(next);
  };

  return (
    <Stack gap={2}>
      <SwitchField
        label={t('settings.general.enableMcpp')}
        checked={mcpEnabled}
        onChange={(checked) => { setMcpEnabled(checked); mcpSaver.change(checked); }}
        disabled={mcpLoading || mcpSaver.state.phase === 'saving'}
      />
      <SaveStatus state={mcpSaver.state} />
      <Text fontSize="xs" color="whiteAlpha.600">
        {t('settings.general.enableMcppHelp')}
      </Text>
      {mcpLoadError && (
        <Text fontSize="xs" color="red.300">{mcpLoadError}</Text>
      )}

      {engine && !engine.available && (
        <Text fontSize="xs" color="orange.300">{engine.reason}</Text>
      )}
      {backgroundDraft && (
        <Stack gap={1}>
          <Text fontSize="xs" color="whiteAlpha.600">
            {t('settings.general.engineBackgroundHelp')}
          </Text>
          <InputField
            label={t('settings.general.engineBackgroundUrl')}
            value={backgroundDraft.url}
            onChange={(value) => changeBackground('url', value)}
            onBlur={backgroundSaver.flush}
            placeholder="http://127.0.0.1:1235/v1"
          />
          <InputField
            label={t('settings.general.engineBackgroundModel')}
            value={backgroundDraft.model}
            onChange={(value) => changeBackground('model', value)}
            onBlur={backgroundSaver.flush}
            placeholder="qwen/qwen3.5-9b"
          />
          <SaveStatus state={backgroundSaver.state} />
        </Stack>
      )}
      {engineError && (
        <Text fontSize="xs" color="red.300">{engineError}</Text>
      )}
    </Stack>
  );
}

export default ModelExtras;
