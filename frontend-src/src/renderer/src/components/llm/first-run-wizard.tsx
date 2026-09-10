/* eslint-disable import/no-extraneous-dependencies */
// 首次啟動精靈：<LlmForm> 的全螢幕包裝。跟設定分頁版（sidebar/setting/llm.tsx）
// 共用同一個表單元件——差別只在「什麼時候出現」與「多一個跳過／關閉的殼」。
//
// 顯示條件是「後端就緒 AND 未設定」，不是「頁面載入」：app 自帶 renderer，
// 視窗會在後端就緒前出現。在 wsState 變成 'OPEN' 之前不呼叫 fetchLlmConfig
// ——太早呼叫只會拿到網路錯誤，無法分辨「未設定」跟「後端還沒起來」。
//
// fetchLlmConfig 失敗（ok:false）時不顯示精靈：寧可漏顯示，也不要在後端有問題
// 時擋住整個畫面——精靈漏顯示還有設定分頁可以補救，擋住畫面沒有退路。
//
// 「先跳過」的選擇存 localStorage，否則每次啟動都會再問一次。

import { useEffect, useState } from 'react';
import { Box, Stack, Heading, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { useWebSocket } from '@/context/websocket-context';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { fetchLlmConfig, type LlmSaveResult } from '@/api/llm-config.ts';
import LlmForm from './llm-form';
import AvatarKindStep from './avatar-kind-step';
import { useSwitchCharacter } from '@/hooks/utils/use-switch-character';

const SKIP_STORAGE_KEY = 'setupWizardSkipped';

// 未設定與否只在後端第一次回報 'OPEN' 之後查一次。查完就是查完——不重試、
// 不輪詢。失敗或已設定都會讓精靈永久不出現（僅限這次 session），跟其他
// 兩種狀態一樣不需要之後再檢查。
type CheckState = 'pending' | 'unconfigured' | 'done';

function FirstRunWizard(): JSX.Element | null {
  const { t } = useTranslation();
  const { wsState, baseUrl } = useWebSocket();
  const [skipped, setSkipped] = useLocalStorage<boolean>(SKIP_STORAGE_KEY, false);
  const [checkState, setCheckState] = useState<CheckState>('pending');
  // 存檔成功後的「已完成」畫面只存在這個 session 裡，不寫 localStorage——
  // 下次真正重啟後，後端會重新讀 conf.yaml，is_configured 屆時自然變 true，
  // 顯示條件本身就會擋掉精靈，不需要額外的持久旗標。
  const [savedResult, setSavedResult] = useState<LlmSaveResult | null>(null);
  const [dismissed, setDismissed] = useState(false);
  // LLM 存好之後多問一步「2D 還是 3D」。兩種模型都隨附了，但預設角色寫死指向
  // Live2D，不去角色設定翻的人不會知道有 3D。AvatarKindStep 在沒得選（只有一種
  // 類型）或查詢失敗時會自己呼叫 onDone，所以這裡不必重複判斷。
  const [avatarPicked, setAvatarPicked] = useState(false);
  // 必須在下面的提早 return 之前呼叫——hook 的數量每次渲染都要一樣，放在 return
  // null 之後的話，精靈從隱藏變顯示那一次會多一個 hook，React 直接讓整個 app 崩潰。
  const { reloadCharacter } = useSwitchCharacter();

  useEffect(() => {
    if (wsState !== 'OPEN' || checkState !== 'pending') {
      return undefined;
    }
    let cancelled = false;
    (async () => {
      const result = await fetchLlmConfig(baseUrl);
      if (cancelled) return;
      if (result.ok && result.data.is_configured === false) {
        setCheckState('unconfigured');
      } else {
        setCheckState('done');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [wsState, baseUrl, checkState]);

  if (skipped || dismissed || checkState !== 'unconfigured') {
    return null;
  }

  const handleSkip = (): void => setSkipped(true);
  // 精靈裡存了 LLM、也可能換了 2D/3D 外觀。關掉時請後端重讀一次，兩者立刻生效，
  // 不用再叫使用者重啟。
  const handleClose = (): void => {
    if (savedResult) reloadCharacter();
    setDismissed(true);
  };

  return (
    <Box
      position="fixed"
      inset={0}
      zIndex={2000}
      bg="blackAlpha.900"
      overflowY="auto"
      display="flex"
      alignItems="center"
      justifyContent="center"
      p={6}
    >
      <Stack
        maxW="480px"
        width="100%"
        gap={6}
        bg="gray.900"
        borderRadius="lg"
        p={8}
        boxShadow="dark-lg"
      >
        <Stack gap={2}>
          <Heading size="md">{t('setup.title')}</Heading>
          <Text fontSize="sm" color="whiteAlpha.700">
            {t('setup.intro')}
          </Text>
        </Stack>

        {savedResult && !avatarPicked ? (
          <AvatarKindStep baseUrl={baseUrl} onDone={() => setAvatarPicked(true)} />
        ) : savedResult ? (
          <Stack gap={4}>
            <Stack gap={1}>
              <Text fontWeight="bold">{t('setup.savedTitle')}</Text>
              <Text fontSize="sm" color="whiteAlpha.700">
                {t('setup.savedReady')}
              </Text>
            </Stack>
            <Button tone="blue" onClick={handleClose} className="self-start">
              {t('setup.startChatting')}
            </Button>
          </Stack>
        ) : (
          <Stack gap={4}>
            <LlmForm onSaved={setSavedResult} />
            <Button variant="ghost" onClick={handleSkip} className="self-start">
              {t('setup.skip')}
            </Button>
          </Stack>
        )}
      </Stack>
    </Box>
  );
}

export default FirstRunWizard;
