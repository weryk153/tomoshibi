/* eslint-disable import/no-extraneous-dependencies */
/* eslint-disable react-hooks/rules-of-hooks */
// 這個分頁分成三塊，跟 asr.tsx 同一種「一部分走 Apply/Revert、其餘自己即時
// 存檔」的模式（見 asr.tsx 檔頭說明）：
// - 畫布互動設定（pointerInteractive／scrollToResize）：走 ，抽屜
//   關閉時由 handleCancel 還原。TabActions 就放在這一塊裡面，視覺上它管到哪
//   裡一目了然。
// - 舞台特效預覽與入場音樂：按下去就播、上傳就存，不可還原。
// - 動作設定（MotionConfig）：寫的是 model_dict.json 的 motionMap／tapMotions，
//   後端狀態、即時存檔。
// 後兩塊刻意不接進 TabActions——2e 子專案整批就是在消滅「一顆按鈕看起來管全部」
// 的混淆，每一塊都有自己的標題與常駐說明文字把界線講清楚。
import {
  Box, Button, Heading, Input, Stack, Text,
} from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { settingStyles } from './setting-styles';
import { useLive2dSettings } from '@/hooks/sidebar/setting/use-live2d-settings';
import { SwitchField } from './common';
import { useStageEffect } from '@/context/stage-effect-context';
import { resolveStageEffectCharacterId } from '@/effects/stage-effect-bindings';
import {
  getStageEffectMusic,
  removeStageEffectMusic,
  saveStageEffectMusic,
  StageEffectMusicError,
} from '@/effects/stage-effect-music';
import { toaster } from '@/components/ui/tw/toaster';
import MotionConfig from './motion-config';
import VrmConfigSummary from './vrm-config-summary';

function live2D(): JSX.Element {
  const { t } = useTranslation();
  const { playEffect } = useStageEffect();
  const {
    modelInfo,
    handleInputChange,
  } = useLive2dSettings();
  const characterId = resolveStageEffectCharacterId(modelInfo);
  const [musicFileName, setMusicFileName] = useState<string | null>(null);
  const [isSavingMusic, setIsSavingMusic] = useState(false);

  useEffect(() => {
    let active = true;
    if (!characterId) {
      setMusicFileName(null);
      return undefined;
    }
    getStageEffectMusic(characterId, 'characterEntrance')
      .then((record) => {
        if (active) setMusicFileName(record?.fileName || null);
      })
      .catch(() => {
        if (active) setMusicFileName(null);
      });
    return () => {
      active = false;
    };
  }, [characterId]);

  const showMusicError = (error: StageEffectMusicError | 'saveFailed') => {
    toaster.create({
      title: t(`settings.live2d.musicErrors.${error}`),
      type: 'error',
      duration: 2500,
    });
  };

  const handleMusicFile = async (file: File | undefined) => {
    if (!file || !characterId) return;
    setIsSavingMusic(true);
    try {
      const invalid = await saveStageEffectMusic(
        characterId,
        'characterEntrance',
        file,
      );
      if (invalid) {
        showMusicError(invalid);
        return;
      }
      setMusicFileName(file.name);
      toaster.create({
        title: t('settings.live2d.musicSaved'),
        type: 'success',
        duration: 2000,
      });
    } catch {
      showMusicError('saveFailed');
    } finally {
      setIsSavingMusic(false);
    }
  };

  const handleRemoveMusic = async () => {
    if (!characterId) return;
    try {
      await removeStageEffectMusic(characterId, 'characterEntrance');
      setMusicFileName(null);
    } catch {
      showMusicError('saveFailed');
    }
  };

  return (
    <Stack {...settingStyles.common.container}>
      <Stack gap={2}>
        <Heading size="sm">{t('settings.live2d.previewSettingsSectionTitle')}</Heading>
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.live2d.previewSettingsSectionDesc')}</Text>

        <SwitchField
          label={t('settings.live2d.pointerInteractive')}
          checked={modelInfo.pointerInteractive ?? false}
          onChange={(checked) => handleInputChange('pointerInteractive', checked)}
        />

        <SwitchField
          label={t('settings.live2d.scrollToResize')}
          checked={modelInfo.scrollToResize ?? true}
          onChange={(checked) => handleInputChange('scrollToResize', checked)}
        />

        {/* 「滑鼠互動」管的其實只有點擊播動作（use-live2d-model 的
            allowTapMotion），跟視線跟隨無關——名字容易誤會，所以視線另外給一個
            開關，而不是塞進同一個。 */}
        <SwitchField
          label={t('settings.live2d.lookAtPointer')}
          help={t('settings.live2d.lookAtPointerDesc')}
          checked={modelInfo.lookAtPointer ?? true}
          onChange={(checked) => handleInputChange('lookAtPointer', checked)}
        />
      </Stack>

      <Box
        borderWidth="1px"
        borderColor="whiteAlpha.200"
        borderRadius="lg"
        p="4"
      >
        <Text fontWeight="semibold">{t('settings.live2d.effectPreviewTitle')}</Text>
        <Text mt="1" mb="3" fontSize="sm" color="fg.muted">
          {t('settings.live2d.effectPreviewDescription')}
        </Text>
        <Stack direction="row" gap="2" flexWrap="wrap">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => playEffect('characterEntrance', {
              scale: 'accent',
              sound: false,
            })}
          >
            {t('settings.live2d.accentPreviewButton')}
          </Button>
          <Button
            size="sm"
            colorPalette="red"
            onClick={() => playEffect('characterEntrance')}
          >
            {t('settings.live2d.entrancePreviewButton')}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => playEffect('cinematicBurst')}
          >
            {t('settings.live2d.effectPreviewButton')}
          </Button>
        </Stack>
        <Box mt="4" pt="4" borderTopWidth="1px" borderColor="whiteAlpha.200">
          <Text fontSize="sm" fontWeight="semibold">
            {t('settings.live2d.entranceMusicLabel')}
          </Text>
          <Text mt="1" mb="2" fontSize="xs" color="fg.muted">
            {musicFileName
              ? t('settings.live2d.entranceMusicCurrent', { name: musicFileName })
              : t('settings.live2d.entranceMusicHelp')}
          </Text>
          <Input
            type="file"
            size="sm"
            accept=".mp3,.wav,.ogg,.m4a,audio/mpeg,audio/wav,audio/ogg,audio/mp4"
            disabled={!characterId || isSavingMusic}
            onChange={(event) => {
              const file = event.currentTarget.files?.[0];
              handleMusicFile(file);
              event.currentTarget.value = '';
            }}
          />
          {musicFileName && (
            <Button
              mt="2"
              size="xs"
              variant="ghost"
              onClick={handleRemoveMusic}
            >
              {t('settings.live2d.entranceMusicRemove')}
            </Button>
          )}
        </Box>
      </Box>

      {modelInfo?.type === 'vrm' ? <VrmConfigSummary /> : <MotionConfig />}
    </Stack>
  );
}

export default live2D;
