/* eslint-disable import/no-extraneous-dependencies */
// VRM 版的動作／表情對應編輯器，取代原本唯讀的 vrm-config-summary.tsx。版面與
// 存檔規則照 motion-config.tsx（Live2D 版）：每一列即時存檔、多重對應只顯示
// 第一筆、其餘原樣帶回，見該檔案檔頭的完整說明——這裡不重複，只記 VRM 特有的
// 差異：
// - 沒有 (group, index)／HitArea／tapMotions，VRM 的動作只有 clip 檔名可以定位，
//   點擊區域指派這個區塊完全不存在。
// - idle 是保留字：待機流程直接用檔名 "idle" 找 .vrma（見後端
//   build_vrm_model_config），不像 Live2D 用 reserved 旗標標記任意 (group,
//   index)——這裡永遠鎖住 clip.clip === 'idle' 那一列的輸入框。
// - 表情只列「情緒」：嘴型／眨眼／視線／neutral 從清單裡濾掉
//   （api/vrm-config.ts 的 emotionPresets），理由見那個檔案的註解。
// - 試播不是呼叫 LAppAdapter，是 getActiveRenderer()——VRM 的 renderer 是
//   VRMRenderer，跟 Live2D 走的是 character-renderer.ts 這個共用介面
//   （previewExpression／previewMotion 是可選方法，任何沒實作的 renderer 就是
//   不支援試播，見該介面的註解）。
import {
  useState, useEffect, useMemo, useCallback,
} from 'react';
import { Stack, Box, Text, Heading, HStack } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { useLive2DConfig } from '@/context/live2d-config-context';
import { getActiveRenderer } from '@/avatar/character-renderer';
import { InputField } from './common';
import { validateKeyword } from '@/api/live2d-config.ts';
import {
  fetchVrmModelConfig,
  saveVrmModelConfig,
  buildVrmPayload,
  emotionPresets,
  type VrmModelConfig,
  type VrmClipMapping,
  type VrmMotionRowEdit,
} from '@/api/vrm-config.ts';

function VrmMotionConfig(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const live2DConfig = useLive2DConfig();
  const modelName = live2DConfig.modelInfo?.name;

  const [config, setConfig] = useState<VrmModelConfig | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 動作（clip）：key 是 clip 名稱——VRM 沒有 Live2D 的 (group, index)，clip
  // 名稱本身已經是穩定唯一的鍵，不需要 motion-config.tsx 的 motionKey() 那種
  // 組合鍵技巧。
  const [rows, setRows] = useState<Record<string, VrmMotionRowEdit>>({});
  const [extraMappings, setExtraMappings] = useState<Record<string, VrmClipMapping[]>>({});
  const [orphans, setOrphans] = useState<VrmModelConfig['orphan_keywords']>([]);

  // 表情（情緒 preset）：key 是 preset 名稱。
  const [expressionRows, setExpressionRows] = useState<Record<string, string>>({});
  const [extraEmotionKeywords, setExtraEmotionKeywords] = useState<Record<string, string[]>>({});

  const [saving, setSaving] = useState(false);

  // 試播／回到原樣是否可用：renderer 存在，且（試播另外要求）它有實作
  // previewExpression／previewMotion 這兩個可選方法。用輪詢而不是只在掛載時
  // 檢查一次——這個分頁可能在 VRM 模型還沒載入、renderer 還沒註冊前就被打開，
  // 跟 motion-config.tsx 的 modelReady 同一個理由（見該檔案的說明）。
  const [rendererReady, setRendererReady] = useState(false);
  const [previewReady, setPreviewReady] = useState(false);
  useEffect(() => {
    const check = (): void => {
      const renderer = getActiveRenderer();
      setRendererReady(renderer != null);
      setPreviewReady(
        renderer != null
          && typeof renderer.previewExpression === 'function'
          && typeof renderer.previewMotion === 'function',
      );
    };
    check();
    const id = setInterval(check, 1000);
    return (): void => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!modelName) {
      setConfig(null);
      setLoadError(null);
      return undefined;
    }
    let cancelled = false;
    setConfig(null);
    setLoadError(null);
    (async () => {
      const result = await fetchVrmModelConfig(baseUrl, modelName);
      if (cancelled) return;
      if (result.ok) {
        setConfig(result.data);

        const nextRows: Record<string, VrmMotionRowEdit> = {};
        const nextExtra: Record<string, VrmClipMapping[]> = {};
        result.data.clips.forEach((clip) => {
          const [first, ...rest] = clip.mappings;
          nextRows[clip.clip] = { keyword: first?.keyword ?? '', label: first?.label ?? '' };
          if (rest.length) nextExtra[clip.clip] = rest;
        });
        setRows(nextRows);
        setExtraMappings(nextExtra);
        setOrphans(result.data.orphan_keywords);

        const nextExpressionRows: Record<string, string> = {};
        const nextExtraEmotion: Record<string, string[]> = {};
        emotionPresets(result.data).forEach((expression) => {
          const [first, ...rest] = expression.keywords;
          nextExpressionRows[expression.name] = first ?? '';
          if (rest.length) nextExtraEmotion[expression.name] = rest;
        });
        setExpressionRows(nextExpressionRows);
        setExtraEmotionKeywords(nextExtraEmotion);
      } else {
        setLoadError(result.error || t('settings.live2d.motionConfigLoadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, modelName]);

  const handleMotionPreview = useCallback((clip: string) => {
    getActiveRenderer()?.previewMotion?.(clip);
  }, []);

  const handleExpressionPreview = useCallback((name: string) => {
    getActiveRenderer()?.previewExpression?.(name);
  }, []);

  const handleResetExpression = useCallback(() => {
    getActiveRenderer()?.resetExpression();
  }, []);

  const allKeywordsExcept = useCallback((excludeClip: string): string[] => {
    const list: string[] = [];
    Object.entries(rows).forEach(([clip, row]) => {
      if (clip === excludeClip) return;
      const trimmed = row.keyword.trim();
      if (trimmed) list.push(trimmed);
    });
    Object.values(extraMappings).forEach((mappings) => {
      mappings.forEach((m) => list.push(m.keyword));
    });
    return list;
  }, [rows, extraMappings]);

  // 空白不是錯誤——代表「這個動作還沒指定關鍵字」，是正常狀態。
  const rowError = useCallback((clip: string): 'duplicate' | 'invalidChars' | null => {
    const row = rows[clip];
    if (!row || row.keyword.trim() === '') return null;
    const result = validateKeyword(row.keyword, allKeywordsExcept(clip));
    return result === 'empty' ? null : result;
  }, [rows, allKeywordsExcept]);

  const allEmotionKeywordsExcept = useCallback((excludeName: string): string[] => {
    const list: string[] = [];
    Object.entries(expressionRows).forEach(([name, keyword]) => {
      if (name === excludeName) return;
      const trimmed = keyword.trim();
      if (trimmed) list.push(trimmed);
    });
    Object.entries(extraEmotionKeywords).forEach(([name, keywords]) => {
      if (name === excludeName) return;
      keywords.forEach((k) => list.push(k));
    });
    return list;
  }, [expressionRows, extraEmotionKeywords]);

  const expressionRowError = useCallback((name: string): 'duplicate' | 'invalidChars' | null => {
    const keyword = expressionRows[name];
    if (!keyword || keyword.trim() === '') return null;
    const result = validateKeyword(keyword, allEmotionKeywordsExcept(name));
    return result === 'empty' ? null : result;
  }, [expressionRows, allEmotionKeywordsExcept]);

  const presets = useMemo(() => (config ? emotionPresets(config) : []), [config]);

  const hasAnyError = useMemo(() => {
    if (!config) return false;
    // 動作跟表情共用同一顆存檔按鈕（同一個 PUT、同一份 model_dict.json）——
    // 任何一邊有錯都要擋下整次存檔，跟 motion-config.tsx 同一個理由。
    return config.clips.some((clip) => rowError(clip.clip) !== null)
      || presets.some((expression) => expressionRowError(expression.name) !== null);
  }, [config, presets, rowError, expressionRowError]);

  const handleSave = useCallback(async () => {
    if (!config || !modelName || hasAnyError) return;
    setSaving(true);
    const { motionMap, emotionMap } = buildVrmPayload(
      config.clips, rows, extraMappings, presets, expressionRows, extraEmotionKeywords,
    );
    const result = await saveVrmModelConfig(baseUrl, modelName, motionMap, emotionMap);
    setSaving(false);
    if (result.ok) {
      // orphan_keywords 從來不會被 buildVrmPayload 包進去，這次存檔已經把它們
      // 從 model_dict.json 移除了——畫面上的清單要跟著清空。
      setOrphans([]);
      toaster.create({
        title: t('settings.live2d.motionConfigSaved'),
        type: 'success',
        duration: 3000,
      });
    } else {
      toaster.create({
        title: result.error || t('settings.live2d.motionConfigSaveFailed'),
        type: 'error',
        duration: 4000,
      });
    }
  }, [
    config, modelName, hasAnyError, rows, extraMappings, presets,
    expressionRows, extraEmotionKeywords, baseUrl, t,
  ]);

  return (
    <Stack gap={2}>
      <Heading size="sm">{t('settings.live2d.motionConfigSectionTitle')}</Heading>
      <Text fontSize="xs" color="blue.300">{t('settings.live2d.motionConfigSectionNote')}</Text>
      <Text fontSize="xs" color="whiteAlpha.600">{t('settings.live2d.vrmMotionSectionNote')}</Text>

      {!modelName && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.motionConfigNoModel')}</Text>
      )}

      {modelName && loadError && (
        <Text fontSize="sm" color="red.300">{loadError}</Text>
      )}

      {modelName && !loadError && !config && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.motionConfigLoading')}</Text>
      )}

      {config && !config.has_idle && (
        <Text fontSize="sm" color="orange.300">{t('settings.live2d.vrmNoIdle')}</Text>
      )}

      {config && config.clips.length === 0 && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.motionConfigEmpty')}</Text>
      )}

      {config && orphans.length > 0 && (
        <Box borderWidth="1px" borderColor="orange.700" borderRadius="md" p={2}>
          <Text fontSize="sm" color="orange.300">{t('settings.live2d.orphanWarningTitle')}</Text>
          <Stack gap={1} mt={1}>
            {orphans.map((orphan) => (
              <Text key={`${orphan.keyword}-${orphan.clip ?? ''}`} fontSize="xs" color="whiteAlpha.700">
                {`「${orphan.keyword}」→ ${orphan.clip ?? t('settings.live2d.groupUnnamed')}`}
              </Text>
            ))}
          </Stack>
          <Button
            size="xs"
            tone="orange"
            variant="outline"
            className="mt-2"
            onClick={handleSave}
            loading={saving}
          >
            {t('settings.live2d.orphanClearButton')}
          </Button>
        </Box>
      )}

      {config && config.clips.map((clip) => {
        const row = rows[clip.clip] ?? { keyword: '', label: '' };
        const error = rowError(clip.clip);
        const isIdle = clip.clip === 'idle';
        return (
          <Box key={clip.clip} p={2} borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="md">
            <HStack justify="space-between">
              <Text fontSize="sm" fontWeight="semibold">{clip.clip}</Text>
              {isIdle && (
                <Text fontSize="xs" color="orange.300">{t('settings.live2d.reservedBadge')}</Text>
              )}
            </HStack>
            <Text fontSize="xs" color="whiteAlpha.500">
              {t('settings.live2d.vrmClipFileLabel')}
              ：
              {clip.file}
            </Text>
            {isIdle && (
              <Text fontSize="xs" color="whiteAlpha.500">{t('settings.live2d.reservedHelp')}</Text>
            )}

            <HStack mt={1} gap={2}>
              <Button
                size="xs"
                variant="outline"
                onClick={() => handleMotionPreview(clip.clip)}
                disabled={!previewReady}
              >
                {t('settings.live2d.previewButton')}
              </Button>
              {!previewReady && (
                <Text fontSize="xs" color="whiteAlpha.500">{t('settings.live2d.previewDisabledReason')}</Text>
              )}
            </HStack>

            <InputField
              label={t('settings.live2d.keywordFieldLabel')}
              value={row.keyword}
              onChange={(value) => setRows((prev) => ({
                ...prev,
                [clip.clip]: { keyword: value, label: prev[clip.clip]?.label ?? '' },
              }))}
              placeholder={t('settings.live2d.keywordFieldPlaceholder')}
              disabled={isIdle}
            />
            {error && (
              <Text fontSize="xs" color="red.300">
                {t(error === 'duplicate'
                  ? 'settings.live2d.keywordErrorDuplicate'
                  : 'settings.live2d.keywordErrorInvalidChars')}
              </Text>
            )}

            <InputField
              label={t('settings.live2d.labelFieldLabel')}
              value={row.label}
              onChange={(value) => setRows((prev) => ({
                ...prev,
                [clip.clip]: { keyword: prev[clip.clip]?.keyword ?? '', label: value },
              }))}
              placeholder={t('settings.live2d.labelFieldPlaceholder')}
              disabled={isIdle}
            />
          </Box>
        );
      })}

      {config && (
        <Stack gap={2} mt={2}>
          <Heading size="sm">{t('settings.live2d.expressionSectionTitle')}</Heading>
          <Text fontSize="xs" color="whiteAlpha.600">{t('settings.live2d.vrmEmotionSectionNote')}</Text>

          {presets.length === 0 ? (
            <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.expressionNone')}</Text>
          ) : (
            <>
              <HStack>
                <Button
                  size="xs"
                  variant="outline"
                  onClick={handleResetExpression}
                  disabled={!rendererReady}
                >
                  {t('settings.live2d.expressionResetButton')}
                </Button>
                {!rendererReady && (
                  <Text fontSize="xs" color="whiteAlpha.500">{t('settings.live2d.previewDisabledReason')}</Text>
                )}
              </HStack>

              {presets.map((expression) => {
                const keyword = expressionRows[expression.name] ?? '';
                const error = expressionRowError(expression.name);
                const extras = extraEmotionKeywords[expression.name] ?? [];
                return (
                  <Box
                    key={expression.name}
                    p={2}
                    borderWidth="1px"
                    borderColor="whiteAlpha.200"
                    borderRadius="md"
                  >
                    <HStack justify="space-between">
                      <Text fontSize="sm" fontWeight="semibold">
                        {t('settings.live2d.vrmExpressionPresetLabel')}
                        ：
                        {expression.name}
                      </Text>
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => handleExpressionPreview(expression.name)}
                        disabled={!previewReady}
                      >
                        {t('settings.live2d.previewButton')}
                      </Button>
                    </HStack>

                    <InputField
                      label={t('settings.live2d.emotionKeywordFieldLabel')}
                      value={keyword}
                      onChange={(value) => setExpressionRows((prev) => ({
                        ...prev,
                        [expression.name]: value,
                      }))}
                      placeholder={t('settings.live2d.emotionKeywordFieldPlaceholder')}
                    />
                    {error && (
                      <Text fontSize="xs" color="red.300">
                        {t(error === 'duplicate'
                          ? 'settings.live2d.keywordErrorDuplicate'
                          : 'settings.live2d.keywordErrorInvalidChars')}
                      </Text>
                    )}
                    {extras.length > 0 && (
                      <Text fontSize="xs" color="whiteAlpha.500">
                        {t('settings.live2d.emotionKeywordExtras', { keywords: extras.join('、') })}
                      </Text>
                    )}
                  </Box>
                );
              })}
            </>
          )}
        </Stack>
      )}

      {config && (
        <Button
          size="sm"
          tone="blue"
          className="self-start"
          onClick={handleSave}
          loading={saving}
          disabled={hasAnyError}
        >
          {t('common.save')}
        </Button>
      )}
    </Stack>
  );
}

export default VrmMotionConfig;
