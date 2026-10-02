// 舞台頁的特效預覽與登場配樂。配樂跟著畫面上的角色（模型）存在瀏覽器裡；
// 演出方案沒有指定配樂時，登場就用這一首。
import { Box, Button, Input, Stack, Text } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { useStageEffect } from '@/context/stage-effect-context';
import { resolveStageEffectCharacterId } from '@/effects/stage-effect-bindings';
import {
  getStageEffectMusic,
  removeStageEffectMusic,
  saveStageEffectMusic,
  StageEffectMusicError,
} from '@/effects/stage-effect-music';
import { toaster } from '@/components/ui/tw/toaster';

function StageEffects(): JSX.Element {
  const { t } = useTranslation();
  const { playEffect } = useStageEffect();
  const { modelInfo } = useLive2DConfig();
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
  );
}

export default StageEffects;
