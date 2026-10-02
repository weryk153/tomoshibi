// 舞台頁的「畫布互動」：滑鼠點擊播動作、滾輪縮放、視線跟隨。寫 localStorage，
// 立刻生效；Live2D 與 VRM 都吃這三個。
import { Stack, Text } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { useLive2dSettings } from '@/hooks/sidebar/setting/use-live2d-settings';
import { interactionSettingsOf } from '@/utils/canvas-interaction';
import { SwitchField } from './common';

function CanvasInteraction(): JSX.Element {
  const { t } = useTranslation();
  const { modelInfo, handleInputChange } = useLive2dSettings();
  // 沒設過的開關顯示實際行為（開著），不是關著。
  const settings = interactionSettingsOf(modelInfo);

  return (
    <Stack gap={2}>
      <Text fontSize="xs" color="whiteAlpha.600">{t('settings.live2d.previewSettingsSectionDesc')}</Text>

      <SwitchField
        label={t('settings.live2d.pointerInteractive')}
        checked={settings.pointerInteractive}
        onChange={(checked) => handleInputChange('pointerInteractive', checked)}
      />

      <SwitchField
        label={t('settings.live2d.scrollToResize')}
        checked={settings.scrollToResize}
        onChange={(checked) => handleInputChange('scrollToResize', checked)}
      />

      {/* 「滑鼠互動」管的其實只有點擊播動作（use-live2d-model 的
          allowTapMotion），跟視線跟隨無關——名字容易誤會，所以視線另外給一個
          開關，而不是塞進同一個。 */}
      <SwitchField
        label={t('settings.live2d.lookAtPointer')}
        help={t('settings.live2d.lookAtPointerDesc')}
        checked={settings.lookAtPointer}
        onChange={(checked) => handleInputChange('lookAtPointer', checked)}
      />
    </Stack>
  );
}

export default CanvasInteraction;
