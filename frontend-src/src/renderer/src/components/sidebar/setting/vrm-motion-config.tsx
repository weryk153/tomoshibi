// VRM 版的動作／表情對應編輯器，取代原本唯讀的 vrm-config-summary.tsx。版面
// 照 motion-config.tsx（Live2D 版）：多重對應只顯示第一筆、其餘原樣帶回，見該
// 檔案檔頭的完整說明——這裡不重複，只記 VRM 特有的差異：
// - 改了就存：編輯先改本地 state，停手一下由 useAutosave（motionSaver）PUT 出去，
//   跟 Live2D 版一樣，沒有「儲存」按鈕。
// - 沒有 (group, index)／HitArea／tapMotions，VRM 的動作只有 clip 檔名可以定位，
//   點擊區域指派這個區塊完全不存在。
// - idle 是保留字，待機流程直接用檔名 "idle" 找 .vrma（見後端
//   build_vrm_model_config），但後端 list_vrm_clips（vrm_models.py）掃描時就
//   把它排除了——這份清單永遠不會出現 idle，不需要 Live2D 版 reserved 旗標那套
//   鎖輸入框的邏輯（review a0c0ce7 fix 4）。buildVrmPayload 仍然留著
//   `clip.clip === 'idle'` 的防呆（見該函式），是防手改 model_dict.json 塞進去
//   的極端情況，不是這個 UI 平常會走到的路。
// - 表情只列「情緒」：嘴型／眨眼／視線／neutral 從清單裡濾掉
//   （api/vrm-config.ts 的 emotionPresets），理由見那個檔案的註解。存檔時這些
//   被濾掉的 preset 原樣帶回（hiddenEmotionKeywords，見下面 state 宣告），不是
//   直接丟棄——這是 review a0c0ce7 fix 1（critical）：這裡是每個 VRM 模型出廠
//   就有的 neutral→neutral 的唯一防線，漏了就會在第一次存檔時被整份洗掉。
// - 試播不是呼叫 LAppAdapter，是 getActiveRenderer()——VRM 的 renderer 是
//   VRMRenderer，跟 Live2D 走的是 character-renderer.ts 這個共用介面
//   （previewExpression／previewMotion 是可選方法，任何沒實作的 renderer 就是
//   不支援試播，見該介面的註解）。previewMotion 是非同步的：VRM 角色載入時只
//   預先讀 motionMap 裡當時有的 clip，剛存檔、還沒試播過的 clip 要現拉，見
//   VRMRenderer.previewMotion 的說明（review a0c0ce7 fix 2）。
import {
  useState, useEffect, useMemo, useCallback, useRef,
} from 'react';
import { Stack, Box, Text, Heading, HStack } from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { SaveStatus } from '@/components/ui/tw/save-status';
import { useAutosave } from '@/hooks/use-autosave';
import { useWebSocket } from '@/context/websocket-context';
import { getActiveRenderer } from '@/avatar/character-renderer';
import { InputField } from './common';
import { validateKeyword } from '@/api/live2d-config.ts';
import {
  fetchVrmModelConfig,
  saveVrmModelConfig,
  buildVrmPayload,
  emotionPresets,
  emotionKeywordsExcept,
  EMOTION_EXCLUDED_PRESETS,
  type VrmModelConfig,
  type VrmClipMapping,
  type VrmMotionRowEdit,
} from '@/api/vrm-config.ts';

interface VrmMotionConfigProps {
  // 要編輯哪個模型（角色頁選中的角色用的那個）。不一定是畫面上那個。
  modelName: string | undefined
  // 它是不是畫面上正在顯示的模型：只有它能試播、回到原樣。
  isLoaded: boolean
}

function VrmMotionConfig({ modelName, isLoaded }: VrmMotionConfigProps): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();

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
  // review a0c0ce7 fix 1（critical）：emotionPresets 濾掉的 preset（嘴型／眨眼／
  // 視線／neutral）完全沒有畫面可以編輯，但幾乎每個 VRM 模型出廠就有
  // neutral→neutral（kurisu_3d 系列甚至整份 emotionMap 都指向被排除的
  // preset）。載入時把這些關鍵字整份存起來，存檔時原樣帶回 buildVrmPayload，
  // 不然第一次存檔就會把它們全部洗掉。key 是 preset 名稱，value 是這個
  // preset 當時讀到的完整關鍵字清單。
  const [hiddenEmotionKeywords, setHiddenEmotionKeywords] = useState<Record<string, string[]>>({});

  // 存檔是非同步的（http.ts 的 timeout 是 15 秒），回來時使用者可能已經在角色
  // 分頁換掉模型了。載入 effect 有 cancelled flag，存檔這邊原本什麼都沒有——
  // A 的 PUT 回來會把 B 的失效關鍵字警告清掉（但 B 的檔案沒動），並拿 A 的
  // clip 名去叫 B 的 ensureMotionLoaded 要不存在的 .vrma。用一個永遠指向
  // 「畫面上現在是哪個模型」的 ref 當守衛。
  const currentModelRef = useRef(modelName);
  useEffect(() => {
    currentModelRef.current = modelName;
  }, [modelName]);

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
  // 不是畫面上的模型就不能試播：按下去會播在另一個模型身上。
  const canPreview = isLoaded && previewReady;
  const canReset = isLoaded && rendererReady;

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

        // 被 emotionPresets 濾掉的 preset：整份關鍵字清單原樣存起來，畫面沒有
        // 欄位可以編輯它們，存檔時要整份帶回（見上面 state 宣告的說明）。
        const nextHiddenEmotion: Record<string, string[]> = {};
        result.data.expressions.forEach((expression) => {
          if (EMOTION_EXCLUDED_PRESETS.has(expression.name) && expression.keywords.length) {
            nextHiddenEmotion[expression.name] = expression.keywords;
          }
        });
        setHiddenEmotionKeywords(nextHiddenEmotion);
      } else {
        setLoadError(result.error || t('settings.live2d.motionConfigLoadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, modelName]);

  // previewMotion 可能要現拉還沒載入過的 .vrma（見 VRMRenderer.previewMotion 的
  // 說明），所以是非同步。false 代表角色根本沒有這個 clip 檔案——不是靜靜地
  // 什麼都不做，要讓使用者知道。
  const handleMotionPreview = useCallback(async (clip: string) => {
    // 'superseded' 是「載入還沒回來就被下一次試播取代」，那是使用者自己又點了
    // 別的動作，不是錯誤，不能彈「這個角色沒有這個動作」（見 PreviewMotionResult）。
    const result = await getActiveRenderer()?.previewMotion?.(clip);
    if (result === 'missing') {
      toaster.create({
        title: t('settings.live2d.vrmPreviewClipMissing'),
        type: 'error',
        duration: 4000,
      });
    }
  }, [t]);

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

  // re-review of cfa0138 殘留 1：重複檢查的清單一定要包含 hiddenEmotionKeywords
  // （被 emotionPresets 濾掉、畫面看不到的既有關鍵字，例如 neutral→neutral）。
  // 漏了它，使用者在可見列打「neutral」不會被判重複，存檔時兩個來源會撞同一個
  // key（見 api/vrm-config.ts 的 emotionKeywordsExcept 說明）。邏輯本體已經抽成
  // 純函式方便單獨測試（vrm-config.test.ts），這裡只是把元件的 state 餵進去。
  const allEmotionKeywordsExcept = useCallback(
    (excludeName: string): string[] => emotionKeywordsExcept(
      excludeName, expressionRows, extraEmotionKeywords, hiddenEmotionKeywords,
    ),
    [expressionRows, extraEmotionKeywords, hiddenEmotionKeywords],
  );

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

  const saveConfig = useCallback(async () => {
    if (!config || !modelName) return { ok: true } as const;
    const { motionMap, emotionMap } = buildVrmPayload(
      config.clips, rows, extraMappings, presets, expressionRows, extraEmotionKeywords,
      hiddenEmotionKeywords,
    );
    const savedModel = modelName;
    const result = await saveVrmModelConfig(baseUrl, modelName, motionMap, emotionMap);
    // 存檔本身成功與否照常回報（那是真的發生過的事），但只有在畫面還停在同一個
    // 模型時才把結果套回 state／renderer。
    const stillCurrent = currentModelRef.current === savedModel;
    if (result.ok) {
      // orphan_keywords 從來不會被 buildVrmPayload 包進去，這次存檔已經把它們
      // 從 model_dict.json 移除了——畫面上的清單要跟著清空。只清自己這次存的
      // 那個模型的，別把已經換上來的另一個模型的警告一起抹掉。
      if (stillCurrent) setOrphans([]);
      // review a0c0ce7 fix 2(d)：角色載入當下只預先讀了 motionMap 裡「當時」有
      // 的 clip（見 vrm-avatar.tsx）。這裡對存檔後 motionMap 裡「每一個」clip
      // 都呼叫 ensureMotionLoaded（不只挑新增的）——ensureLoaded 內部用
      // hasClip 短路，已經載入過的一律立刻 resolve(true) 不重拉，逐一呼叫全部
      // 比自己再算一次「哪些是新的」便宜、也不會算漏。不 await，不擋存檔完成
      // 的回饋；用 Promise.allSettled 收集而不是各自裸接，讓「這裡不會 throw」
      // 是結構上保證的，不是依賴 ensureMotionLoaded 目前剛好每條路徑都不拋
      // （re-review of cfa0138 殘留 3）。
      // 同理，getActiveRenderer() 是現拉的：模型換過就是另一顆 renderer，拿
      // 這次存的 clip 名去叫它只會去要一批不存在的 .vrma。
      if (stillCurrent) {
        const renderer = getActiveRenderer();
        const clipsToPreload = [...new Set(Object.values(motionMap).map((target) => target.clip))];
        void Promise.allSettled(clipsToPreload.map((clip) => renderer?.ensureMotionLoaded?.(clip)));
      }
      return { ok: true } as const;
    }
    return { ok: false, error: result.error || t('settings.live2d.motionConfigSaveFailed') } as const;
  }, [
    config, modelName, rows, extraMappings, presets,
    expressionRows, extraEmotionKeywords, hiddenEmotionKeywords, baseUrl, t,
  ]);

  // 改了就存（停手 0.8 秒）；有不合法的列就不送並說明原因。
  const motionSaver = useAutosave(async (snapshot: string) => {
    void snapshot;
    return saveConfig();
  }, {
    validate: () => (hasAnyError ? t('settings.live2d.motionConfigFixErrors') : null),
  });

  // 載入後的第一份不算；之後任何一欄改了就排一次存檔（存檔器只送最後那份）。
  const loadedRef = useRef(false);
  useEffect(() => {
    loadedRef.current = false;
  }, [modelName]);
  useEffect(() => {
    if (!config) return;
    if (!loadedRef.current) {
      loadedRef.current = true;
      return;
    }
    motionSaver.change(JSON.stringify([
      rows, extraMappings, expressionRows, extraEmotionKeywords, hiddenEmotionKeywords,
    ]));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config, rows, extraMappings, expressionRows, extraEmotionKeywords, hiddenEmotionKeywords]);

  return (
    <Stack gap={2}>
      <Heading size="sm">{t('settings.live2d.motionConfigSectionTitle')}</Heading>
      <Text fontSize="xs" color="blue.300">{t('settings.live2d.motionConfigSectionNote')}</Text>
      <Text fontSize="xs" color="whiteAlpha.600">{t('settings.live2d.vrmMotionSectionNote')}</Text>
      <SaveStatus state={motionSaver.state} />

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
          <Text fontSize="sm" color="orange.300">{t('settings.live2d.vrmOrphanWarningTitle')}</Text>
          <Stack gap={1} mt={1}>
            {orphans.map((orphan) => (
              <Text key={`${orphan.kind ?? 'motion'}-${orphan.keyword}-${orphan.clip ?? ''}`} fontSize="xs" color="whiteAlpha.700">
                {orphan.kind === 'expression'
                  ? t('settings.live2d.vrmOrphanExpressionItem', {
                    keyword: orphan.keyword,
                    name: orphan.clip ?? t('settings.live2d.vrmOrphanUnknownClip'),
                  })
                  : t('settings.live2d.vrmOrphanWarningItem', {
                    keyword: orphan.keyword,
                    clip: orphan.clip ?? t('settings.live2d.vrmOrphanUnknownClip'),
                  })}
              </Text>
            ))}
          </Stack>
          <Button
            size="xs"
            tone="orange"
            variant="outline"
            className="mt-2"
            // 存一次就會把孤兒對應從 model_dict.json 拿掉（它們不在送出的 payload 裡）。
            onClick={() => { motionSaver.change(`clear-orphans-${Date.now()}`); motionSaver.flush(); }}
            loading={motionSaver.state.phase === 'saving'}
            disabled={hasAnyError}
          >
            {t('settings.live2d.orphanClearButton')}
          </Button>
        </Box>
      )}

      {/* review a0c0ce7 fix 4：list_vrm_clips（vrm_models.py）排除 idle——它是待機
          迴圈專用的檔名，從來不會出現在這份清單裡，所以這裡不需要（也不該有）
          Live2D 版 reserved／isIdle 那一整套鎖輸入框的邏輯。 */}
      {config && config.clips.map((clip) => {
        const row = rows[clip.clip] ?? { keyword: '', label: '' };
        const error = rowError(clip.clip);
        return (
          <Box key={clip.clip} p={2} borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="md">
            <Text fontSize="sm" fontWeight="semibold">{clip.clip}</Text>
            <Text fontSize="xs" color="whiteAlpha.500">
              {t('settings.live2d.vrmClipFileLabel', { file: clip.file })}
            </Text>

            <HStack mt={1} gap={2}>
              <Button
                size="xs"
                variant="outline"
                onClick={() => handleMotionPreview(clip.clip)}
                disabled={!canPreview}
              >
                {t('settings.live2d.previewButton')}
              </Button>
              {!canPreview && (
                <Text fontSize="xs" color="whiteAlpha.500">{isLoaded ? t('settings.live2d.previewDisabledReason') : t('settings.live2d.previewNotOnScreen')}</Text>
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
                  disabled={!canReset}
                >
                  {t('settings.live2d.expressionResetButton')}
                </Button>
                {!canReset && (
                  <Text fontSize="xs" color="whiteAlpha.500">{isLoaded ? t('settings.live2d.previewDisabledReason') : t('settings.live2d.previewNotOnScreen')}</Text>
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
                        {t('settings.live2d.vrmExpressionPresetLabel', { name: expression.name })}
                      </Text>
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => handleExpressionPreview(expression.name)}
                        disabled={!canPreview}
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

    </Stack>
  );
}

export default VrmMotionConfig;
