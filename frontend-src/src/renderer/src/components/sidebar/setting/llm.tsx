import { useState } from 'react';
import { Stack, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import LlmForm from '../../llm/llm-form';
import { settingStyles } from './setting-styles';
import type { LlmSaveResult } from '@/api/llm-config.ts';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';

// 設定分頁版的 LLM 表單。不接 onSave/onCancel——存檔是即時的（按 Test & Save
// 就直接寫入 conf.yaml），跟 TTS／About 一樣是無 props 的分頁，沒有東西可以讓
// 外層的抽屜 Save 按鈕去觸發。
//
// 存檔成功後送 reload-config，請後端重讀 conf.yaml 與目前的角色，新的 LLM 立刻
// 生效。POST /api/llm-config 仍回傳 restart_required: true（它自己不會重載），
// 所以不能省掉這一步——少了它，畫面說好了、角色卻還在用舊的 LLM。
function LLM(): JSX.Element {
  const { t } = useTranslation();
  const [saved, setSaved] = useState<LlmSaveResult | null>(null);

  const { reloadCharacter } = useSwitchCharacter();
  const handleSaved = (result: LlmSaveResult): void => {
    setSaved(result);
    reloadCharacter();
  };

  return (
    <Stack {...settingStyles.common.container}>
      <LlmForm onSaved={handleSaved} onApplied={reloadCharacter} />
      {saved && (
        <Stack gap={1}>
          <Text fontWeight="bold">{t('setup.savedTitle')}</Text>
          <Text fontSize="sm" color="whiteAlpha.700">
            {t('setup.savedReady')}
          </Text>
        </Stack>
      )}
    </Stack>
  );
}

export default LLM;
