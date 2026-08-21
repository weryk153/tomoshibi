/* eslint-disable import/no-extraneous-dependencies */
// 動作清單與試播（3a-2 Task 4）：讓使用者看到模型「真的有」的每一個動作
// （不是 model_dict.json 手寫出來的那份），播放確認長什麼樣子，再指定
// 觸發用的關鍵字與顯示名稱。
//
// 這個區塊是後端狀態、即時存檔，刻意不接進 live2d.tsx 既有的
// TabActions（Apply/Revert）——那一對按鈕governs的是 pointerInteractive／
// scrollToResize 兩個畫布互動設定，走抽屜關閉時的還原機制；這裡寫的是
// model_dict.json，語意完全不同。2e 子專案整批就是在消滅「一顆按鈕看起來
// 管全部、其實只管一半」的混淆，不能在這裡重演。分界用常駐文字
// （motionConfigSectionNote）講清楚，不是操作完才彈一次的 toast。
//
// 存檔的形狀：PUT 端點整份取代 motionMap／tapMotions（見
// live2d_config_route.py write_model_config 的 docstring），所以每次存檔
// 都要把「目前畫面上看得到的每一列」+「原本就存在、這個 UI 沒有畫面可編輯
// 的額外 mapping（同一個動作被兩個以上的關鍵字指到）」一起重新組裝出完整
// 的 motionMap，不能只送目前正在編輯的那一列，否則等於用這次存檔把其他
// 關鍵字全部清空。
//
// orphan_keywords（motionMap 指向的 (group,index) 已經不存在於目前的
// model3.json）不可能被合法送回——_validate_motion_map 會直接拒絕任何指向
// 不存在動作的目標，回 400。所以這裡的「清除失效的關鍵字」其實就是呼叫
// 同一個 handleSave：因為 buildMotionMap 本來就只從 config.motions 重建，
// orphan 從來不會被包進去，這個按鈕只是把「存檔會順便丟掉它們」這件事對
// 使用者講清楚，而不是另外一個獨立的清除 API（沒有這種 API）。
//
// 點擊區域指派（3a-2 Task 5）：讓 tapMotions 能指到單一動作，不再只能指到
// 一整個群組再隨機——mao_pro 六個可用動作全在同一個無名群組，改版前點頭跟
// 點身體是同一種隨機結果。畫面上每個 HitArea 一組候選清單（動作＋權重），
// 跟上面的關鍵字／顯示名稱共用同一個 handleSave／PUT，兩者本來就是同一份
// model_dict.json 的兩個欄位。
import {
  useState, useEffect, useMemo, useCallback,
} from 'react';
import { Stack, Box, Text, Heading, HStack } from '@chakra-ui/react';
import { createListCollection } from '@ark-ui/react/collection';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { useLive2DConfig } from '@/context/live2d-config-context';
// 表情的「回到原樣」沿用 app 自己那條路（解除目前表情，不是套一個中性表情
// 上去），跟 AI 回到閒置時走的是同一個函式。
import { useLive2DExpression } from '@/hooks/canvas/use-live2d-expression';
import { InputField, NumberField, SelectField } from './common';
// 先確認過真實的匯入路徑與 alias（tsconfig.web.json／electron.vite.config.ts）：
// WebSDK/src 底下的模組是用 @cubismsdksamples/* 這個 alias，不是
// @/renderer/WebSDK/src/*——後者在這個專案裡根本不存在，會編譯失敗。
import { LAppAdapter } from '@cubismsdksamples/lappadapter';
import {
  fetchModelConfig,
  saveModelConfig,
  validateKeyword,
  type ModelConfig,
  type MotionEntry,
  type MotionMapping,
  type MotionMapTarget,
  type OrphanKeyword,
  type TapMotionEntry,
} from '@/api/live2d-config.ts';

// (group, index) 的畫面用 key，只拿來當 Record 的字串鍵、不需要反解析。用
// JSON.stringify 而不是字串相接（例如 `${group}-${index}`）——group 是任意
// 字串，相接法在 group 本身包含分隔字元時可能讓兩個不同的 (group, index)
// 撞成同一個 key，畫面上會有兩列共用同一份編輯狀態、其中一個的 mapping
// 存檔時悄悄消失。JSON.stringify(['a', 1]) 對每個相異的 (group, index)
// 組合都是唯一字串，沒有這個問題。同一個 key 也拿來當點擊區域區塊「選一個
// 動作加入」下拉選單的 value——這裡的 index 一定是 number（來自 Task 1 列舉
// 出來的 config.motions，從未有 null），跟 tapMotions 條目自己的
// index: number | null 是兩回事，不要混用。
function motionKey(motion: { group: string; index: number }): string {
  return JSON.stringify([motion.group, motion.index]);
}

interface RowEdit {
  keyword: string
  label: string
}

function MotionConfig(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const live2DConfig = useLive2DConfig();
  const modelName = live2DConfig.modelInfo?.name;

  const [config, setConfig] = useState<ModelConfig | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [rows, setRows] = useState<Record<string, RowEdit>>({});
  // 每個動作除了畫面上這一列以外、原本就存在的其他 mapping（同一個動作被
  // 不只一個關鍵字指到）。這個 UI 沒有畫面可以編輯它們，但存檔時必須原樣
  // 保留，不能因為畫面沒顯示就悄悄弄丟。
  const [extraMappings, setExtraMappings] = useState<Record<string, MotionMapping[]>>({});
  const [orphans, setOrphans] = useState<OrphanKeyword[]>([]);
  const [saving, setSaving] = useState(false);

  // 點擊區域指派：hitAreaId -> 目前指派的候選清單（畫面上的即時編輯狀態，
  // 存檔前都只改這裡，不動 config.tap_motions）。初始值是這次 GET 到的
  // tap_motions 原樣複製，往後的每次加入／移除／改權重都是不可變更新。
  const [tapMotionEdits, setTapMotionEdits] = useState<Record<string, TapMotionEntry[]>>({});
  // 每個 hitArea 自己的「準備加入哪個動作」草稿——選好但還沒按加入之前的
  // 暫存狀態，key 是 hitArea id，value 是 motionKey(...) 字串。空字串代表
  // 還沒選。
  const [draftMotionKey, setDraftMotionKey] = useState<Record<string, string>>({});

  // 表情的情緒關鍵字：表情索引 -> 畫面上正在編輯的關鍵字。空字串代表「這個
  // 表情還沒命名」，是正常狀態，存檔時整個不放進 emotionMap。
  const { resetExpression } = useLive2DExpression();
  const [expressionRows, setExpressionRows] = useState<Record<number, string>>({});
  // 同一個表情被第二個以上關鍵字指到時，多出來的那些。畫面只給一個輸入框
  // （跟動作那半一樣），但存檔要原樣帶回去，不能因為 UI 只顯示一個就把使用者
  // 手寫在 model_dict.json 裡的其他關鍵字洗掉。
  const [extraEmotionKeywords, setExtraEmotionKeywords] = useState<Record<number, string[]>>({});

  // 模型是否已經在畫面上初始化（LAppAdapter.getInstance().getModel() 非
  // null）。試播鍵必須反映這個真實狀態並停用＋顯示原因，不能按下去悄悄沒
  // 反應——所以用輪詢而不是只在掛載時檢查一次：這個分頁可能在 Live2D 模型
  // 還沒載入完成前就被打開。
  const [modelReady, setModelReady] = useState(false);
  useEffect(() => {
    const check = (): void => setModelReady(LAppAdapter.getInstance().getModel() != null);
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
      const result = await fetchModelConfig(baseUrl, modelName);
      if (cancelled) return;
      if (result.ok) {
        setConfig(result.data);
        const nextRows: Record<string, RowEdit> = {};
        const nextExtra: Record<string, MotionMapping[]> = {};
        result.data.motions.forEach((motion) => {
          const key = motionKey(motion);
          const [first, ...rest] = motion.mappings;
          nextRows[key] = { keyword: first?.keyword ?? '', label: first?.label ?? '' };
          if (rest.length) nextExtra[key] = rest;
        });
        setRows(nextRows);
        setExtraMappings(nextExtra);
        setOrphans(result.data.orphan_keywords);
        setTapMotionEdits(result.data.tap_motions);
        setDraftMotionKey({});

        const nextExpressions: Record<number, string> = {};
        const nextExtraEmotion: Record<number, string[]> = {};
        result.data.expressions.forEach((expression) => {
          const [first, ...rest] = expression.keywords;
          nextExpressions[expression.index] = first ?? '';
          if (rest.length) nextExtraEmotion[expression.index] = rest;
        });
        setExpressionRows(nextExpressions);
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

  const handlePreview = useCallback((motion: MotionEntry) => {
    const model = LAppAdapter.getInstance().getModel();
    if (!model) return;
    // PriorityForce (3)，跟 use-live2d-motion.ts 的 LLM 觸發路徑同一個優先度
    // ——試播也該蓋過目前可能正在播的待機/說話動作，不然會看起來沒反應。
    model.startMotion(motion.group, motion.index, 3);
  }, []);

  // 表情試套。跟 use-live2d-expression.ts 的 LLM 觸發路徑一樣是「用名字設定」
  // ——setExpression 吃的是表情名稱字串，不是索引；索引要先經 getExpressionName
  // 轉換。這裡直接拿後端列舉出來的 name，省掉那一步。
  const handleExpressionPreview = useCallback((expressionName: string) => {
    const adapter = LAppAdapter.getInstance();
    if (!adapter.getModel()) return;
    adapter.setExpression(expressionName);
  }, []);

  // 畫面上（不含 index 本身這一列）所有非空的情緒關鍵字。跟動作那半分開比對
  // ——後端 _validate_emotion_map 與 _validate_motion_map 也是各驗各的，兩個
  // 是不同的字典，同一個字同時當動作和表情的關鍵字並不衝突。
  const allEmotionKeywordsExcept = useCallback((excludeIndex: number): string[] => {
    const list: string[] = [];
    Object.entries(expressionRows).forEach(([index, keyword]) => {
      if (Number(index) === excludeIndex) return;
      const trimmed = keyword.trim();
      if (trimmed) list.push(trimmed);
    });
    Object.entries(extraEmotionKeywords).forEach(([index, keywords]) => {
      if (Number(index) === excludeIndex) return;
      keywords.forEach((k) => list.push(k));
    });
    return list;
  }, [expressionRows, extraEmotionKeywords]);

  // 空白不是錯誤（＝還沒命名），只有真的打了字才檢查。
  const expressionRowError = useCallback((index: number): 'duplicate' | 'invalidChars' | null => {
    const keyword = expressionRows[index];
    if (!keyword || keyword.trim() === '') return null;
    const result = validateKeyword(keyword, allEmotionKeywordsExcept(index));
    return result === 'empty' ? null : result;
  }, [expressionRows, allEmotionKeywordsExcept]);

  // 從畫面狀態重建整份 emotionMap（PUT 是整份取代）。空白的表情不放進去，
  // 多出來的關鍵字原樣帶回。
  const buildEmotionMap = useCallback((): Record<string, number> => {
    const map: Record<string, number> = {};
    Object.entries(expressionRows).forEach(([index, keyword]) => {
      const trimmed = keyword.trim();
      if (trimmed) map[trimmed] = Number(index);
    });
    Object.entries(extraEmotionKeywords).forEach(([index, keywords]) => {
      keywords.forEach((k) => {
        const trimmed = k.trim();
        if (trimmed) map[trimmed] = Number(index);
      });
    });
    return map;
  }, [expressionRows, extraEmotionKeywords]);

  // 目前畫面上（不含 key 本身這一列）所有非空關鍵字，不分大小寫比對用——
  // 跟後端 live2d_config_route.py 的 _validate_motion_map 同一個規則。
  const allKeywordsExcept = useCallback((excludeKey: string): string[] => {
    const list: string[] = [];
    Object.entries(rows).forEach(([key, row]) => {
      if (key === excludeKey) return;
      const trimmed = row.keyword.trim();
      if (trimmed) list.push(trimmed);
    });
    Object.values(extraMappings).forEach((mappings) => {
      mappings.forEach((m) => list.push(m.keyword));
    });
    return list;
  }, [rows, extraMappings]);

  // 空白關鍵字不是錯誤——代表「這個動作還沒指定關鍵字」，是正常狀態，不
  // 該顯示紅字。只有使用者已經打了字、但那個字不合法/重複時才報錯。
  const rowError = useCallback((key: string): 'duplicate' | 'invalidChars' | null => {
    const row = rows[key];
    if (!row || row.keyword.trim() === '') return null;
    const result = validateKeyword(row.keyword, allKeywordsExcept(key));
    return result === 'empty' ? null : result;
  }, [rows, allKeywordsExcept]);

  const hasAnyError = useMemo(() => {
    if (!config) return false;
    // 動作跟表情共用同一顆存檔按鈕（同一個 PUT、同一份 model_dict.json），
    // 所以任何一邊有錯都要擋下整次存檔——只擋一半會讓另一半悄悄寫進去。
    return config.motions.some((motion) => rowError(motionKey(motion)) !== null)
      || config.expressions.some((expression) => expressionRowError(expression.index) !== null);
  }, [config, rowError, expressionRowError]);

  const buildMotionMap = useCallback((): Record<string, MotionMapTarget> => {
    const map: Record<string, MotionMapTarget> = {};
    if (!config) return map;
    config.motions.forEach((motion) => {
      const key = motionKey(motion);
      const row = rows[key];
      const trimmedKeyword = row?.keyword.trim();
      if (trimmedKeyword) {
        const trimmedLabel = row.label.trim();
        map[trimmedKeyword] = {
          group: motion.group,
          index: motion.index,
          label: trimmedLabel || null,
        };
      }
      (extraMappings[key] ?? []).forEach((extra) => {
        map[extra.keyword] = { group: motion.group, index: motion.index, label: extra.label };
      });
    });
    return map;
  }, [config, rows, extraMappings]);

  // 幫某個點擊區域加入一個新候選：{group, index} 取自 Task 1 列舉出來的
  // config.motions（永遠是具體的 (group, index)，index 不會是 null——
  // null 只會出現在既有、從 legacy {group: weight} 正規化過來的資料裡）。
  // 權重預設 1，加入後可以在畫面上用 NumberField 調整。
  const addTapMotionCandidate = useCallback((hitAreaId: string, motion: MotionEntry) => {
    setTapMotionEdits((prev) => ({
      ...prev,
      [hitAreaId]: [...(prev[hitAreaId] ?? []), { group: motion.group, index: motion.index, weight: 1 }],
    }));
  }, []);

  const removeTapMotionCandidate = useCallback((hitAreaId: string, entryIndex: number) => {
    setTapMotionEdits((prev) => ({
      ...prev,
      [hitAreaId]: (prev[hitAreaId] ?? []).filter((_, i) => i !== entryIndex),
    }));
  }, []);

  const updateTapMotionWeight = useCallback((hitAreaId: string, entryIndex: number, weight: number) => {
    setTapMotionEdits((prev) => ({
      ...prev,
      [hitAreaId]: (prev[hitAreaId] ?? []).map(
        (entry, i) => (i === entryIndex ? { ...entry, weight } : entry),
      ),
    }));
  }, []);

  const handleSave = useCallback(async () => {
    if (!config || !modelName || hasAnyError) return;
    setSaving(true);
    const motionMap = buildMotionMap();
    const result = await saveModelConfig(
      baseUrl, modelName, motionMap, tapMotionEdits, buildEmotionMap(),
    );
    setSaving(false);
    if (result.ok) {
      // orphan_keywords 從來不會被 buildMotionMap 包進去，所以這次存檔已經
      // 把它們從 model_dict.json 移除了——畫面上的清單要跟著清空。
      setOrphans([]);
      // 把這次存檔用的 tapMotions（可能剛被點擊區域區塊改過）原樣寫回
      // context，讓點擊行為讀到的資料跟這次存檔後的檔案內容一致。不需要
      // 再轉換成任何「舊版」形狀——Live2DConfigContext 的 TapMotionMap
      // 從 Task 5 起就是 {hitAreaId: [{group,index,weight}]}，跟這裡的
      // tapMotionEdits、後端回應／PUT 請求體的 tap_motions 是同一個形狀，
      // 也是 model.startTapMotion（WebSDK/src/lappmodel.ts）從 Task 5 起
      // 直接吃的形狀。刻意不呼叫 set-model-and-conf 或任何會重載模型的
      // 路徑——存一個關鍵字就讓角色重新載入一次是不能接受的，後端已經就地
      // 刷新共用的 Live2dModel 了。
      //
      // setModelInfo now stores the renderer scale verbatim.  Scale conversion is
      // performed only when a fresh backend model enters websocket-handler, so a
      // motion-map save cannot accidentally resize or reload the current model.
      if (live2DConfig.modelInfo) {
        live2DConfig.setModelInfo({
          ...live2DConfig.modelInfo,
          tapMotions: tapMotionEdits,
        });
      }
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
  }, [config, modelName, hasAnyError, buildMotionMap, buildEmotionMap, baseUrl, live2DConfig, t, tapMotionEdits]);

  // 「選一個動作加入點擊區域」下拉選單共用同一份清單，來源是 Task 1 列舉出
  // 來的 config.motions（模型真實擁有的每個動作），不是 model_dict.json
  // 手寫出來的那份。label 沿用跟上面動作清單同一種寫法：group 為空字串時
  // 顯示 groupUnnamed，不能對 group 做 truthy 測試（空字串是合法群組名，
  // 不是「沒有群組」——mao_pro 六個動作全用空字串）。
  const motionCollection = useMemo(() => createListCollection({
    items: (config?.motions ?? []).map((motion) => ({
      value: motionKey(motion),
      label: `${motion.group === '' ? t('settings.live2d.groupUnnamed') : motion.group} #${motion.index}`,
    })),
  }), [config, t]);

  return (
    <Stack gap={2}>
      <Heading size="sm">{t('settings.live2d.motionConfigSectionTitle')}</Heading>
      {/* 常駐文字，不是 toast：這個區塊自己存檔，不受上面 TabActions 的
          Apply/Revert 影響，這件事必須隨時可見。 */}
      <Text fontSize="xs" color="blue.300">{t('settings.live2d.motionConfigSectionNote')}</Text>

      {!modelName && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.motionConfigNoModel')}</Text>
      )}

      {modelName && loadError && (
        <Text fontSize="sm" color="red.300">{loadError}</Text>
      )}

      {modelName && !loadError && !config && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.motionConfigLoading')}</Text>
      )}

      {config && config.motions.length === 0 && (
        <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.motionConfigEmpty')}</Text>
      )}

      {config && orphans.length > 0 && (
        <Box borderWidth="1px" borderColor="orange.700" borderRadius="md" p={2}>
          <Text fontSize="sm" color="orange.300">{t('settings.live2d.orphanWarningTitle')}</Text>
          <Stack gap={1} mt={1}>
            {orphans.map((orphan) => (
              <Text key={`${orphan.keyword}-${orphan.group}-${orphan.index}`} fontSize="xs" color="whiteAlpha.700">
                {t('settings.live2d.orphanWarningItem', {
                  keyword: orphan.keyword,
                  group: orphan.group === '' ? t('settings.live2d.groupUnnamed') : orphan.group,
                  index: orphan.index ?? '—',
                })}
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

      {config && config.motions.map((motion) => {
        const key = motionKey(motion);
        const row = rows[key] ?? { keyword: '', label: '' };
        const error = rowError(key);
        return (
          <Box key={key} p={2} borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="md">
            <HStack justify="space-between">
              <Text fontSize="sm" fontWeight="semibold">
                {motion.group === '' ? t('settings.live2d.groupUnnamed') : motion.group}
                {' '}
                #
                {motion.index}
              </Text>
              {motion.reserved && (
                <Text fontSize="xs" color="orange.300">{t('settings.live2d.reservedBadge')}</Text>
              )}
            </HStack>
            <Text fontSize="xs" color="whiteAlpha.500">{motion.file}</Text>
            {motion.reserved && (
              <Text fontSize="xs" color="whiteAlpha.500">{t('settings.live2d.reservedHelp')}</Text>
            )}

            <HStack mt={1} gap={2}>
              <Button
                size="xs"
                variant="outline"
                onClick={() => handlePreview(motion)}
                disabled={!modelReady}
              >
                {t('settings.live2d.previewButton')}
              </Button>
              {!modelReady && (
                <Text fontSize="xs" color="whiteAlpha.500">{t('settings.live2d.previewDisabledReason')}</Text>
              )}
            </HStack>

            <InputField
              label={t('settings.live2d.keywordFieldLabel')}
              value={row.keyword}
              onChange={(value) => setRows((prev) => ({
                ...prev,
                [key]: { keyword: value, label: prev[key]?.label ?? '' },
              }))}
              placeholder={t('settings.live2d.keywordFieldPlaceholder')}
              disabled={motion.reserved}
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
                [key]: { keyword: prev[key]?.keyword ?? '', label: value },
              }))}
              placeholder={t('settings.live2d.labelFieldPlaceholder')}
              disabled={motion.reserved}
            />
          </Box>
        );
      })}

      {config && (
        <Stack gap={2} mt={2}>
          <Heading size="sm">{t('settings.live2d.expressionSectionTitle')}</Heading>
          <Text fontSize="xs" color="whiteAlpha.600">
            {t('settings.live2d.expressionSectionNote')}
          </Text>

          {config.expressions.length === 0 ? (
            <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.expressionNone')}</Text>
          ) : (
            <>
              <HStack>
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => resetExpression(LAppAdapter.getInstance())}
                  disabled={!modelReady}
                >
                  {t('settings.live2d.expressionResetButton')}
                </Button>
                {!modelReady && (
                  <Text fontSize="xs" color="whiteAlpha.500">{t('settings.live2d.previewDisabledReason')}</Text>
                )}
              </HStack>

              {config.expressions.map((expression) => {
                const keyword = expressionRows[expression.index] ?? '';
                const error = expressionRowError(expression.index);
                const extras = extraEmotionKeywords[expression.index] ?? [];
                return (
                  <Box
                    key={expression.index}
                    p={2}
                    borderWidth="1px"
                    borderColor="whiteAlpha.200"
                    borderRadius="md"
                  >
                    <HStack justify="space-between">
                      {/* 索引一定要顯示：emotionMap 存的是索引，model3.json 增刪
                          表情之後索引會整批位移，指到別張臉也不會報錯。名字跟
                          索引並排才看得出來對應是不是還正確。 */}
                      <Text fontSize="sm" fontWeight="semibold">
                        {expression.name || t('settings.live2d.expressionUnnamed')}
                        {' '}
                        #
                        {expression.index}
                      </Text>
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => handleExpressionPreview(expression.name)}
                        disabled={!modelReady || !expression.name}
                      >
                        {t('settings.live2d.previewButton')}
                      </Button>
                    </HStack>

                    <InputField
                      label={t('settings.live2d.emotionKeywordFieldLabel')}
                      value={keyword}
                      onChange={(value) => setExpressionRows((prev) => ({
                        ...prev,
                        [expression.index]: value,
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
        <Stack gap={2} mt={2}>
          <Heading size="sm">{t('settings.live2d.tapAreaSectionTitle')}</Heading>
          {config.hit_areas.length === 0 ? (
            <Text fontSize="sm" color="whiteAlpha.700">{t('settings.live2d.tapAreaNoHitAreas')}</Text>
          ) : (
            config.hit_areas.map((area) => {
              const entries = tapMotionEdits[area.id] ?? [];
              return (
                <Box key={area.id} p={2} borderWidth="1px" borderColor="whiteAlpha.200" borderRadius="md">
                  <Text fontSize="sm" fontWeight="semibold">
                    {/* Name 常常是空字串（model3.json 的 HitAreas[].Name 沒填），
                        這種情況只顯示 Id，不要印出一對空括號。 */}
                    {area.name ? `${area.id} (${area.name})` : area.id}
                  </Text>

                  {entries.length === 0 && (
                    <Text fontSize="xs" color="whiteAlpha.500">{t('settings.live2d.tapAreaEmptyEntries')}</Text>
                  )}

                  {entries.map((entry, entryIndex) => (
                    // eslint-disable-next-line react/no-array-index-key
                    <HStack key={entryIndex} mt={1} gap={2} align="flex-end">
                      <Text fontSize="xs" minW="90px">
                        {entry.group === '' ? t('settings.live2d.groupUnnamed') : entry.group}
                        {' #'}
                        {entry.index === null ? t('settings.live2d.tapAreaIndexRandom') : entry.index}
                      </Text>
                      <Box w="90px">
                        <NumberField
                          label={t('settings.live2d.tapAreaWeightLabel')}
                          value={entry.weight}
                          onChange={(value) => updateTapMotionWeight(area.id, entryIndex, Number(value) || 0)}
                          min={0}
                          step={1}
                        />
                      </Box>
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => removeTapMotionCandidate(area.id, entryIndex)}
                      >
                        {t('settings.live2d.tapAreaRemoveButton')}
                      </Button>
                    </HStack>
                  ))}

                  <HStack mt={2} gap={2} align="flex-end">
                    <Box flex="1">
                      <SelectField
                        label={t('settings.live2d.tapAreaMotionSelectLabel')}
                        value={draftMotionKey[area.id] ? [draftMotionKey[area.id]] : []}
                        onChange={(value) => setDraftMotionKey((prev) => ({
                          ...prev,
                          [area.id]: value[0] ?? '',
                        }))}
                        collection={motionCollection}
                        placeholder={t('settings.live2d.tapAreaMotionSelectPlaceholder')}
                      />
                    </Box>
                    <Button
                      size="xs"
                      onClick={() => {
                        const selectedKey = draftMotionKey[area.id];
                        const motion = config.motions.find((m) => motionKey(m) === selectedKey);
                        if (!motion) return;
                        addTapMotionCandidate(area.id, motion);
                        setDraftMotionKey((prev) => ({ ...prev, [area.id]: '' }));
                      }}
                      disabled={!draftMotionKey[area.id]}
                    >
                      {t('settings.live2d.tapAreaAddButton')}
                    </Button>
                  </HStack>
                </Box>
              );
            })
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

export default MotionConfig;
