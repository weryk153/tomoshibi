/* eslint-disable react-hooks/rules-of-hooks */
// 這個分頁分成三塊，每一塊都改了就存：
// - 畫布互動設定（pointerInteractive／scrollToResize／lookAtPointer）：寫 localStorage，立刻生效。
// - 舞台特效預覽與入場音樂：按下去就播、上傳就存。
// - 動作與表情對應（MotionConfig／VrmMotionConfig）：寫 model_dict.json，停手就存。
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
import VrmMotionConfig from './vrm-motion-config';

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
        <Heading size="sm">
          {t('settings.live2d.previewSettingsSectionTitle')}
          {' '}
          <Text as="span" fontSize="xs" fontWeight="normal" color="whiteAlpha.600">
            {t('settings.live2d.sharedBadge')}
          </Text>
        </Heading>
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
        <Text fontWeight="semibold">
          {t('settings.live2d.effectPreviewTitle')}
          {' '}
          <Text as="span" fontSize="xs" fontWeight="normal" color="whiteAlpha.600">
            {t('settings.live2d.sharedBadge')}
          </Text>
        </Text>
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

      {/* 這一塊是唯一真正依模型分歧的：Live2D 跟 VRM 的動作／表情編輯器版面
          相同（都是關鍵字＋顯示名稱＋試播、即時存檔），但資料模型不同——
          Live2D 是 (group, index)＋HitArea，VRM 只有 clip 檔名、沒有點擊區域，
          所以是兩個各自獨立的元件，不共用同一份 UI 硬塞兩種形狀。上面兩塊
          （畫布互動、特效演出）兩種模型都吃，所以標了「共用」——分頁名稱改成
          中性的「角色外觀」之後，這個區分靠這幾個標籤說清楚。 */}
      <Stack gap={2}>
        <Heading size="sm">
          {modelInfo?.type === 'vrm'
            ? t('settings.live2d.vrmOnlySectionTitle')
            : t('settings.live2d.live2dOnlySectionTitle')}
        </Heading>
        {modelInfo?.type === 'vrm' ? <VrmMotionConfig /> : <MotionConfig />}
      </Stack>
    </Stack>
  );
}

export default live2D;
