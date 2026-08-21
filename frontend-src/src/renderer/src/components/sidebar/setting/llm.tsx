import { useState, useEffect } from 'react';
import { Stack, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import LlmForm from '../../llm/llm-form';
import { settingStyles } from './setting-styles';
import type { LlmSaveResult } from '@/api/llm-config.ts';
import { fetchLlmConfig } from '@/api/llm-config.ts';
import { useWebSocket } from '@/context/websocket-context';

// 設定分頁版的 LLM 表單。不接 onSave/onCancel——存檔是即時的（按 Test & Save
// 就直接寫入 conf.yaml），跟 TTS／About 一樣是無 props 的分頁，沒有東西可以讓
// 外層的抽屜 Save 按鈕去觸發。
//
// 存檔成功後必須顯示需要重啟：POST /api/llm-config 永遠回傳
// restart_required: true，因為後端只在啟動時讀一次 conf.yaml。不顯示這件事，
// 使用者會以為設定已生效，然後困惑為什麼角色還是不會回話。
//
// 故意不用 setup.savedReady——那句「你的 AI 設定好了，可以開始聊天」只在後端
// 能自己重啟（supervisor）之後才成立，屬於之後的子專案。
function LLM(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const [saved, setSaved] = useState<LlmSaveResult | null>(null);

  // 只有在 llm_provider 真的指向別的 provider 時才警告。常駐的免責聲明會被當成
  // 背景雜訊；指名道姓才讀得進去（同 tts.tsx 的角色覆蓋提示）。
  const [inactiveProvider, setInactiveProvider] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await fetchLlmConfig(baseUrl);
      if (cancelled || !result.ok) return;
      const active = result.data.active_provider;
      setInactiveProvider(
        active && active !== 'openai_compatible_llm' ? active : null,
      );
    })();
    return (): void => { cancelled = true; };
  }, [baseUrl]);

  const handleSaved = (result: LlmSaveResult): void => {
    setSaved(result);
  };

  return (
    <Stack {...settingStyles.common.container}>
      {inactiveProvider && (
        <Text fontSize="xs" color="orange.300">
          {t('setup.inactiveProvider', { active: inactiveProvider })}
        </Text>
      )}
      <LlmForm onSaved={handleSaved} />
      {saved && (
        <Stack gap={1}>
          <Text fontWeight="bold">{t('setup.savedTitle')}</Text>
          <Text fontSize="sm" color="whiteAlpha.700">
            {t('setup.savedRestart')}
          </Text>
        </Stack>
      )}
    </Stack>
  );
}

export default LLM;
