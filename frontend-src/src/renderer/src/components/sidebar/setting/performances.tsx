/* eslint-disable import/no-extraneous-dependencies */
import { Box, Button, Heading, HStack, Input, Stack, Text, Textarea } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import {
  useEffect,
  useMemo,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';

import { Field, TextInput, Checkbox } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import {
  NumberField,
  SelectField,
  SwitchField,
} from './common';
import { settingStyles } from './setting-styles';
import { useStagePerformance } from '@/context/stage-performance-context';
import { useScene } from '@/context/scene-context';
import { CURRENT_BACKGROUND_SCENE_ID } from '@/scenes/scene';
import {
  cloneStagePerformancePreset,
  isStagePerformanceCompatible,
  STAGE_PERFORMANCE_MODES,
  STAGE_PERFORMANCE_TRIGGERS,
  STAGE_TIME_PERIODS,
  StagePerformancePreset,
  StagePerformanceTrigger,
} from '@/effects/stage-performance';
import {
  getStageEffectMusic,
  removeStageEffectMusic,
  saveStageEffectMusic,
  StageEffectMusicError,
} from '@/effects/stage-effect-music';

function Performances(): JSX.Element {
  const { t } = useTranslation();
  const {
    characterId,
    presets,
    getPool,
    updatePool,
    duplicatePreset,
    updatePreset,
    deletePreset,
    playPreset,
    previewTrigger,
  } = useStagePerformance();
  const {
    scenes,
    getPerformanceBinding,
    setPerformanceBinding,
  } = useScene();
  const [trigger, setTrigger] = useState<StagePerformanceTrigger>('conversation');
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [draft, setDraft] = useState<StagePerformancePreset | null>(null);
  const [musicFileName, setMusicFileName] = useState<string | null>(null);
  const [isSavingMusic, setIsSavingMusic] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(false);
  const pool = getPool(trigger);

  const compatiblePresets = useMemo(() => presets.filter((preset) => (
    isStagePerformanceCompatible(preset, characterId, trigger)
  )), [characterId, presets, trigger]);

  const selectedPreset = presets.find((preset) => preset.id === selectedPresetId) || null;
  const sceneBinding = selectedPresetId
    ? getPerformanceBinding(selectedPresetId)
    : null;

  useEffect(() => {
    if (
      selectedPresetId
      && !compatiblePresets.some((preset) => preset.id === selectedPresetId)
    ) {
      setSelectedPresetId(null);
      setDraft(null);
    }
  }, [compatiblePresets, selectedPresetId]);

  useEffect(() => {
    setDraft(selectedPreset && !selectedPreset.builtin
      ? cloneStagePerformancePreset(selectedPreset)
      : null);
    setPendingDelete(false);
  }, [selectedPreset]);

  useEffect(() => {
    let active = true;
    if (!characterId || !selectedPresetId) {
      setMusicFileName(null);
      return undefined;
    }
    getStageEffectMusic(characterId, selectedPresetId)
      .then((record) => {
        if (active) setMusicFileName(record?.fileName || null);
      })
      .catch(() => {
        if (active) setMusicFileName(null);
      });
    return () => {
      active = false;
    };
  }, [characterId, selectedPresetId]);

  const triggerCollection = useMemo(() => createListCollection({
    items: STAGE_PERFORMANCE_TRIGGERS.map((value) => ({
      value: String(value),
      label: t(`settings.performances.triggers.${value}`),
    })),
  }), [t]);
  const modeCollection = useMemo(() => createListCollection({
    items: STAGE_PERFORMANCE_MODES.map((value) => ({
      value: String(value),
      label: t(`settings.performances.modes.${value}`),
    })),
  }), [t]);
  const effectCollection = useMemo(() => createListCollection({
    items: [
      { value: 'characterEntrance', label: t('settings.performances.effects.entrance') },
      { value: 'cinematicBurst', label: t('settings.performances.effects.cinematic') },
    ],
  }), [t]);
  const scaleCollection = useMemo(() => createListCollection({
    items: ['accent', 'scene', 'cinematic'].map((value) => ({
      value,
      label: t(`settings.performances.scales.${value}`),
    })),
  }), [t]);
  const sceneCollection = useMemo(() => createListCollection({
    items: [
      { value: 'none', label: t('settings.performances.noScene') },
      ...scenes.map((scene) => ({
        value: scene.id,
        label: scene.id === CURRENT_BACKGROUND_SCENE_ID
          ? t('settings.scenes.currentBackground')
          : scene.name,
      })),
    ],
  }), [scenes, t]);

  const setPresetEnabled = (presetId: string, enabled: boolean) => {
    const selectedIds = enabled
      ? [...new Set([...pool.selectedIds, presetId])]
      : pool.selectedIds.filter((id) => id !== presetId);
    updatePool(trigger, { selectedIds });
  };

  const createCopy = (presetId?: string) => {
    const sourceId = presetId || selectedPresetId || compatiblePresets[0]?.id;
    if (!sourceId) return;
    const newId = duplicatePreset(sourceId);
    if (newId) {
      const sourceSceneBinding = getPerformanceBinding(sourceId);
      if (sourceSceneBinding) {
        setPerformanceBinding(newId, sourceSceneBinding);
      }
      updatePool(trigger, {
        selectedIds: [...new Set([...pool.selectedIds, newId])],
      });
      setSelectedPresetId(newId);
    }
  };

  const saveDraft = () => {
    if (!draft) return;
    updatePreset(draft.id, draft);
    toaster.create({
      title: t('settings.performances.saved'),
      type: 'success',
      duration: 1800,
    });
  };

  const removeDraft = () => {
    if (!draft) return;
    setPerformanceBinding(draft.id, null);
    deletePreset(draft.id);
    setSelectedPresetId(null);
    setDraft(null);
    setPendingDelete(false);
  };

  const showMusicError = (error: StageEffectMusicError | 'saveFailed') => {
    toaster.create({
      title: t(`settings.live2d.musicErrors.${error}`),
      type: 'error',
      duration: 2200,
    });
  };

  const handleMusicFile = async (file: File | undefined) => {
    if (!file || !characterId || !selectedPresetId) return;
    setIsSavingMusic(true);
    try {
      const invalid = await saveStageEffectMusic(
        characterId,
        selectedPresetId,
        file,
      );
      if (invalid) {
        showMusicError(invalid);
        return;
      }
      setMusicFileName(file.name);
    } catch {
      showMusicError('saveFailed');
    } finally {
      setIsSavingMusic(false);
    }
  };

  const removeMusic = async () => {
    if (!characterId || !selectedPresetId) return;
    try {
      await removeStageEffectMusic(characterId, selectedPresetId);
      setMusicFileName(null);
    } catch {
      showMusicError('saveFailed');
    }
  };

  return (
    <Stack {...settingStyles.common.container} maxW="none">
      <Heading size="sm">{t('settings.performances.title')}</Heading>
      <Text fontSize="sm" color="fg.muted">
        {t('settings.performances.description')}
      </Text>

      <Box p="4" borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg">
        <Stack gap="3">
          <SelectField
            label={t('settings.performances.trigger')}
            value={[trigger]}
            onChange={(value) => setTrigger(
              (value[0] || 'conversation') as StagePerformanceTrigger,
            )}
            collection={triggerCollection}
            placeholder={t('settings.performances.trigger')}
          />
          <SwitchField
            label={t('settings.performances.poolEnabled')}
            checked={pool.enabled}
            onChange={(enabled) => updatePool(trigger, { enabled })}
            help={t('settings.performances.poolEnabledHelp')}
          />
          <SelectField
            label={t('settings.performances.playMode')}
            value={[pool.mode]}
            onChange={(value) => updatePool(trigger, {
              mode: (value[0] || 'shuffle') as typeof pool.mode,
            })}
            collection={modeCollection}
            placeholder={t('settings.performances.playMode')}
          />
          <NumberField
            label={t('settings.performances.avoidRecent')}
            value={pool.avoidRecent}
            min={0}
            max={10}
            step={1}
            onChange={(value) => updatePool(trigger, {
              avoidRecent: Number(value),
            })}
          />
          <HStack>
            <Button
              size="sm"
              colorPalette="blue"
              onClick={() => previewTrigger(trigger)}
              disabled={pool.selectedIds.length === 0}
            >
              {t('settings.performances.testPool')}
            </Button>
            <Button size="sm" variant="outline" onClick={() => createCopy()}>
              {t('settings.performances.addFromCopy')}
            </Button>
          </HStack>
          {['ai', 'hybrid'].includes(pool.mode) && (
            <Text fontSize="xs" color="cyan.300">
              {t('settings.performances.aiDirectorHelp')}
            </Text>
          )}
        </Stack>
      </Box>

      <Stack gap="2">
        <Text fontWeight="semibold">
          {t('settings.performances.poolSelection', {
            count: pool.selectedIds.length,
          })}
        </Text>
        {compatiblePresets.map((preset) => {
          const enabled = pool.selectedIds.includes(preset.id);
          const active = selectedPresetId === preset.id;
          return (
            <Box
              key={preset.id}
              p="3"
              borderWidth="1px"
              borderColor={active ? 'blue.400' : 'whiteAlpha.200'}
              borderRadius="md"
            >
              <Stack gap="2">
                <Stack
                  direction={{ base: 'column', md: 'row' }}
                  align={{ base: 'stretch', md: 'start' }}
                  justify="space-between"
                  gap="3"
                >
                  <Checkbox
                    checked={enabled}
                    onCheckedChange={(details) => (
                      setPresetEnabled(preset.id, details.checked === true)
                    )}
                  >
                    <Stack gap="0">
                      <Text fontWeight="semibold">{preset.name}</Text>
                      <Text fontSize="xs" color="whiteAlpha.500">{preset.id}</Text>
                    </Stack>
                  </Checkbox>
                  <HStack flexWrap="wrap">
                    <Button size="xs" onClick={() => playPreset(preset.id)}>
                      {t('settings.performances.preview')}
                    </Button>
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => setSelectedPresetId(preset.id)}
                    >
                      {preset.builtin
                        ? t('settings.performances.details')
                        : t('settings.performances.edit')}
                    </Button>
                  </HStack>
                </Stack>
                <Text fontSize="xs" color="whiteAlpha.600">
                  {preset.description}
                </Text>
              </Stack>
            </Box>
          );
        })}
      </Stack>

      {selectedPreset && (
        <Box p="4" borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="lg">
          <Stack gap="3">
            <HStack justify="space-between">
              <Heading size="xs">{selectedPreset.name}</Heading>
              <Button size="xs" variant="outline" onClick={() => createCopy(selectedPreset.id)}>
                {t('settings.performances.duplicateToEdit')}
              </Button>
            </HStack>

            {selectedPreset.builtin && (
              <Text fontSize="xs" color="orange.300">
                {t('settings.performances.builtinReadonly')}
              </Text>
            )}

            {draft && (
              <>
                <Field label={t('settings.performances.name')}>
                  <TextInput
                    value={draft.name}
                    onChange={(event) => setDraft({
                      ...draft,
                      name: event.target.value,
                    })}
                  />
                </Field>
                <Field label={t('settings.performances.presetDescription')}>
                  <Textarea
                    rows={3}
                    value={draft.description}
                    onChange={(event) => setDraft({
                      ...draft,
                      description: event.target.value,
                    })}
                  />
                </Field>
                <SelectField
                  label={t('settings.performances.effect')}
                  value={[draft.effectId]}
                  onChange={(value) => setDraft({
                    ...draft,
                    effectId: (value[0] || 'characterEntrance') as typeof draft.effectId,
                  })}
                  collection={effectCollection}
                  placeholder={t('settings.performances.effect')}
                />
                <SelectField
                  label={t('settings.performances.scale')}
                  value={[draft.scale]}
                  onChange={(value) => setDraft({
                    ...draft,
                    scale: (value[0] || 'scene') as typeof draft.scale,
                  })}
                  collection={scaleCollection}
                  placeholder={t('settings.performances.scale')}
                />
                <NumberField
                  label={t('settings.performances.intensity')}
                  value={draft.intensity}
                  min={0.35}
                  max={1.5}
                  step={0.05}
                  onChange={(value) => setDraft({
                    ...draft,
                    intensity: Number(value),
                  })}
                />
                <NumberField
                  label={t('settings.performances.weight')}
                  value={draft.weight}
                  min={0.01}
                  max={100}
                  step={0.5}
                  onChange={(value) => setDraft({
                    ...draft,
                    weight: Number(value),
                  })}
                />
                <NumberField
                  label={t('settings.performances.probability')}
                  value={Math.round(draft.probability * 100)}
                  min={0}
                  max={100}
                  step={5}
                  onChange={(value) => setDraft({
                    ...draft,
                    probability: Number(value) / 100,
                  })}
                />
                <NumberField
                  label={t('settings.performances.cooldown')}
                  value={Math.round(draft.cooldownMs / 1000)}
                  min={0}
                  max={86400}
                  step={5}
                  onChange={(value) => setDraft({
                    ...draft,
                    cooldownMs: Number(value) * 1000,
                  })}
                />
                <SwitchField
                  label={t('settings.performances.sound')}
                  checked={draft.sound}
                  onChange={(sound) => setDraft({ ...draft, sound })}
                />
                <NumberField
                  label={t('settings.performances.musicVolume')}
                  value={Math.round(draft.musicVolume * 100)}
                  min={0}
                  max={100}
                  step={5}
                  onChange={(value) => setDraft({
                    ...draft,
                    musicVolume: Number(value) / 100,
                  })}
                />
                <NumberField
                  label={t('settings.performances.musicFadeIn')}
                  value={draft.musicFadeInMs}
                  min={0}
                  max={10000}
                  step={50}
                  onChange={(value) => setDraft({
                    ...draft,
                    musicFadeInMs: Number(value),
                  })}
                />
                <NumberField
                  label={t('settings.performances.musicFadeOut')}
                  value={draft.musicFadeOutMs}
                  min={0}
                  max={10000}
                  step={50}
                  onChange={(value) => setDraft({
                    ...draft,
                    musicFadeOutMs: Number(value),
                  })}
                />
                <SwitchField
                  label={t('settings.performances.currentCharacterOnly')}
                  checked={Boolean(draft.characterIds?.length)}
                  onChange={(currentOnly) => setDraft({
                    ...draft,
                    characterIds: currentOnly && characterId ? [characterId] : undefined,
                  })}
                  disabled={!characterId}
                />
                <Field label={t('settings.performances.titleText')}>
                  <TextInput
                    value={draft.title || ''}
                    onChange={(event) => setDraft({
                      ...draft,
                      title: event.target.value,
                    })}
                  />
                </Field>
                <Field label={t('settings.performances.subtitleText')}>
                  <TextInput
                    value={draft.subtitle || ''}
                    onChange={(event) => setDraft({
                      ...draft,
                      subtitle: event.target.value,
                    })}
                  />
                </Field>
                <Field
                  label={t('settings.performances.keywords')}
                  help={t('settings.performances.keywordsHelp')}
                >
                  <TextInput
                    value={draft.conditions.keywords.join(', ')}
                    onChange={(event) => setDraft({
                      ...draft,
                      conditions: {
                        ...draft.conditions,
                        keywords: event.target.value.split(',')
                          .map((value) => value.trim())
                          .filter(Boolean),
                      },
                    })}
                  />
                </Field>
                <Text fontSize="sm" fontWeight="semibold">
                  {t('settings.performances.allowedTriggers')}
                </Text>
                <HStack flexWrap="wrap">
                  {STAGE_PERFORMANCE_TRIGGERS.map((value) => (
                    <Checkbox
                      key={value}
                      checked={draft.triggers.includes(value)}
                      onCheckedChange={(details) => {
                        const enabled = details.checked === true;
                        setDraft({
                          ...draft,
                          triggers: enabled
                            ? [...new Set([...draft.triggers, value])]
                            : draft.triggers.filter((item) => item !== value),
                        });
                      }}
                    >
                      {t(`settings.performances.triggers.${value}`)}
                    </Checkbox>
                  ))}
                </HStack>
                <Text fontSize="sm" fontWeight="semibold">
                  {t('settings.performances.timePeriods')}
                </Text>
                <HStack flexWrap="wrap">
                  {STAGE_TIME_PERIODS.map((period) => (
                    <Checkbox
                      key={period}
                      checked={draft.conditions.timePeriods.includes(period)}
                      onCheckedChange={(details) => {
                        const enabled = details.checked === true;
                        setDraft({
                          ...draft,
                          conditions: {
                            ...draft.conditions,
                            timePeriods: enabled
                              ? [...new Set([...draft.conditions.timePeriods, period])]
                              : draft.conditions.timePeriods.filter((item) => item !== period),
                          },
                        });
                      }}
                    >
                      {t(`settings.performances.time.${period}`)}
                    </Checkbox>
                  ))}
                </HStack>
                <HStack>
                  <Button colorPalette="blue" size="sm" onClick={saveDraft}>
                    {t('common.save')}
                  </Button>
                  {pendingDelete ? (
                    <>
                      <Text fontSize="xs" color="red.300">
                        {t('settings.performances.confirmDelete')}
                      </Text>
                      <Button colorPalette="red" size="xs" onClick={removeDraft}>
                        {t('settings.performances.delete')}
                      </Button>
                      <Button size="xs" variant="ghost" onClick={() => setPendingDelete(false)}>
                        {t('common.cancel')}
                      </Button>
                    </>
                  ) : (
                    <Button
                      colorPalette="red"
                      size="sm"
                      variant="outline"
                      onClick={() => setPendingDelete(true)}
                    >
                      {t('settings.performances.delete')}
                    </Button>
                  )}
                </HStack>
              </>
            )}

            <Box pt="3" borderTopWidth="1px" borderColor="whiteAlpha.200">
              <Text fontSize="sm" fontWeight="semibold" mb="2">
                {t('settings.performances.scene')}
              </Text>
              <SelectField
                label={t('settings.performances.scene')}
                value={[sceneBinding?.sceneId || 'none']}
                onChange={(value) => {
                  const sceneId = value[0];
                  if (!selectedPresetId) return;
                  setPerformanceBinding(
                    selectedPresetId,
                    !sceneId || sceneId === 'none'
                      ? null
                      : {
                        sceneId,
                        restoreAfter: sceneBinding?.restoreAfter ?? true,
                      },
                  );
                }}
                collection={sceneCollection}
                placeholder={t('settings.performances.noScene')}
              />
              {sceneBinding && (
                <SwitchField
                  label={t('settings.performances.restoreScene')}
                  checked={sceneBinding.restoreAfter}
                  onChange={(restoreAfter) => {
                    if (!selectedPresetId) return;
                    setPerformanceBinding(selectedPresetId, {
                      ...sceneBinding,
                      restoreAfter,
                    });
                  }}
                  help={t('settings.performances.restoreSceneHelp')}
                />
              )}
            </Box>

            <Box pt="3" borderTopWidth="1px" borderColor="whiteAlpha.200">
              <Text fontSize="sm" fontWeight="semibold">
                {t('settings.performances.music')}
              </Text>
              <Text fontSize="xs" color="fg.muted" mb="2">
                {musicFileName || t('settings.performances.noMusic')}
              </Text>
              <Input
                type="file"
                size="sm"
                accept=".mp3,.wav,.ogg,.m4a,audio/mpeg,audio/wav,audio/ogg,audio/mp4"
                disabled={!characterId || isSavingMusic}
                onChange={(event) => {
                  handleMusicFile(event.currentTarget.files?.[0]);
                  event.currentTarget.value = '';
                }}
              />
              {musicFileName && (
                <Button mt="2" size="xs" variant="ghost" onClick={removeMusic}>
                  {t('settings.live2d.entranceMusicRemove')}
                </Button>
              )}
            </Box>
          </Stack>
        </Box>
      )}
    </Stack>
  );
}

export default Performances;
