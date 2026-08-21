/* eslint-disable import/no-extraneous-dependencies */
import { useState, useEffect, useCallback } from 'react';
import {
  Stack, Text, Heading, HStack, Box,
} from '@chakra-ui/react';
import { useTranslation } from 'react-i18next';
import { formatDistanceToNow } from 'date-fns';
import { settingStyles } from './setting-styles';
import { Button } from '@/components/ui/tw/primitives';
import { toaster } from '@/components/ui/tw/toaster';
import { useWebSocket } from '@/context/websocket-context';
import { useAgentSettings } from '@/hooks/sidebar/setting/use-agent-settings';
import {
  SwitchField, NumberField, InputField, } from './common';
import {
  fetchTopics,
  saveTopics,
  refreshNews,
  clampIntervalHours,
  normalizeTopics,
  MAX_TOPICS,
  INTERVAL_HOURS_MIN,
  INTERVAL_HOURS_MAX,
  type TopicsState,
} from '@/api/topics.ts';

// src/open_llm_vtuber/topics_route.py:67 — MAX_TOPIC_LEN, the backend's per-topic
// truncation cap. Task 1's api/topics.ts deliberately doesn't export it (its own
// header says "留給需要它的呼叫端再補" — left for whichever caller needs it to add
// itself). We're that caller: trim the draft client-side before it's ever sent, so
// the user sees exactly what gets saved instead of discovering after a save that the
// backend silently chopped their input.
const MAX_TOPIC_LEN = 200;

function Agent(): JSX.Element {
  const { t } = useTranslation();
  const { baseUrl } = useWebSocket();
  const {
    settings,
    handleAllowProactiveSpeakChange,
    handleIdleSecondsChange,
    handleAllowButtonTriggerChange,
  } = useAgentSettings();

  // 主動話題區塊：後端狀態、即時存檔（見 perf.tsx 同一種模式）。上面那組開關
  // 現在也是即時的，整個分頁只有一種存檔行為。
  const [topics, setTopics] = useState<TopicsState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [newTopicDraft, setNewTopicDraft] = useState('');
  const [savingTopics, setSavingTopics] = useState(false);

  const [intervalDraft, setIntervalDraft] = useState(String(INTERVAL_HOURS_MIN));
  const [savingInterval, setSavingInterval] = useState(false);

  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    (async () => {
      const result = await fetchTopics(baseUrl);
      if (cancelled) return;
      if (result.ok) {
        setTopics(result.data);
        setIntervalDraft(String(result.data.news.interval_hours));
      } else {
        setLoadError(result.error || t('settings.topics.loadError'));
      }
    })();
    return (): void => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl]);

  const atMax = (topics?.topics.length ?? 0) >= MAX_TOPICS;
  const hasNoTopics = (topics?.topics.length ?? 0) === 0;

  // 新增一個話題（手動輸入或點建議 chip 共用這支）。只送改過的 topics 那部分
  // 給 saveTopics（見 api/topics.ts 檔頭的 Partial 語意說明），不連 news 一起
  // 送，避免覆寫使用者可能在別的分頁／裝置剛存的新聞設定。
  const handleAddTopic = useCallback(async (rawValue?: string) => {
    if (!topics) return;
    const value = (rawValue ?? newTopicDraft).trim().slice(0, MAX_TOPIC_LEN);
    if (!value || topics.topics.length >= MAX_TOPICS) return;
    const nextTopics = normalizeTopics([...topics.topics, value]);
    setSavingTopics(true);
    const result = await saveTopics(baseUrl, { topics: nextTopics });
    setSavingTopics(false);
    if (result.ok) {
      setTopics((prev) => (prev ? { ...prev, topics: result.data.topics } : prev));
      if (rawValue === undefined) setNewTopicDraft('');
    } else {
      toaster.create({
        title: result.error || t('settings.topics.saveFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, newTopicDraft, topics, t]);

  const handleRemoveTopic = useCallback(async (topic: string) => {
    if (!topics) return;
    const nextTopics = topics.topics.filter((item) => item !== topic);
    setSavingTopics(true);
    const result = await saveTopics(baseUrl, { topics: nextTopics });
    setSavingTopics(false);
    if (result.ok) {
      setTopics((prev) => (prev ? { ...prev, topics: result.data.topics } : prev));
    } else {
      toaster.create({
        title: result.error || t('settings.topics.saveFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, topics, t]);

  // 新聞開關：離散動作（跟 perf.tsx 的 forever/immediate 模式一樣），切換就
  // 立刻送出，不需要額外的儲存按鈕。
  const handleToggleNews = useCallback(async (checked: boolean) => {
    if (!topics) return;
    const result = await saveTopics(baseUrl, { news: { enabled: checked } });
    if (result.ok) {
      setTopics((prev) => (prev ? { ...prev, news: result.data.news } : prev));
    } else {
      toaster.create({
        title: result.error || t('settings.topics.saveFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, topics, t]);

  // 更新間隔：連續數字輸入，跟 perf.tsx 的自訂秒數草稿一樣，要有自己的儲存
  // 按鈕才送出，不要每敲一下數字就打一次 API。
  const handleIntervalSave = useCallback(async () => {
    const hours = clampIntervalHours(Number(intervalDraft));
    setIntervalDraft(String(hours));
    setSavingInterval(true);
    const result = await saveTopics(baseUrl, { news: { interval_hours: hours } });
    setSavingInterval(false);
    if (result.ok) {
      setTopics((prev) => (prev ? { ...prev, news: result.data.news } : prev));
    } else {
      toaster.create({
        title: result.error || t('settings.topics.saveFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, intervalDraft, t]);

  // 立即抓取：三種結果不可混為一談（見任務簡報）——news_ok===true 才是
  // refreshDone；news_ok===false 但請求本身成功是 refreshFellBack（後端抓不到
  // 新聞、退回用手動話題，是正常結果，不是錯誤）；只有請求本身失敗才是
  // refreshFailed。
  const handleRefreshNow = useCallback(async () => {
    setRefreshing(true);
    const result = await refreshNews(baseUrl);
    setRefreshing(false);
    if (result.ok) {
      setTopics((prev) => (prev ? { ...prev, last_news_refresh: result.data.last_news_refresh } : prev));
      if (result.data.news_ok) {
        toaster.create({
          title: t('settings.topics.refreshDone', { count: result.data.news_count }),
          type: 'success',
          duration: 4000,
        });
      } else {
        toaster.create({
          title: t('settings.topics.refreshFellBack'),
          type: 'info',
          duration: 4000,
        });
      }
    } else {
      toaster.create({
        title: result.error || t('settings.topics.refreshFailed'),
        type: 'error',
        duration: 3000,
      });
    }
  }, [baseUrl, t]);

  return (
    <Stack {...settingStyles.common.container}>
      {/* Apply/Revert 管的三顆開關／欄位：自己的 gap=2 小群組、自己的
          TabActions，跟下面主動話題那個群組用外層 gap=8 隔開——這是 asr.tsx
          區分「上半部 Apply/Revert 治理」與「下半部即時存檔」兩個區塊的同一種
          手法（兩個各自緊湊的 Stack 當外層鬆散 gap 的手足），不是新發明的樣式。
          TabActions 原本放在檔案最底部、topics 區塊之後，畫面上看起來像在管
          topics；use-agent-settings.ts 的 handleCancel 其實只碰這三個欄位，
          所以搬到這裡讓「按鈕管什麼」跟畫面位置對得起來。 */}
      <Stack gap={2}>
        <SwitchField
          label={t('settings.agent.allowProactiveSpeak')}
          checked={settings.allowProactiveSpeak}
          onChange={handleAllowProactiveSpeakChange}
        />

        {settings.allowProactiveSpeak && (
          <NumberField
            label={t('settings.agent.idleSecondsToSpeak')}
            value={settings.idleSecondsToSpeak}
            onChange={(value) => handleIdleSecondsChange(Number(value))}
            min={30}
            step={0.1}
            allowMouseWheel
          />
        )}

        <SwitchField
          label={t('settings.agent.allowButtonTrigger')}
          checked={settings.allowButtonTrigger}
          onChange={handleAllowButtonTriggerChange}
        />
      </Stack>

      {/* 主動話題：後端狀態、即時存檔，走自己的按鈕與狀態提示，不掛進上面的
          TabActions——sectionNote 是常駐文字（不是 toast），跟 asr.tsx 的
          asrEngineSectionNote 同一個作用：讓「這塊歸誰管、還原鍵救不救得到」
          隨時看得到，不用等使用者手滑按了還原才發現話題沒被復原。 */}
      <Stack gap={2}>
        <Heading size="sm">{t('settings.topics.sectionTitle')}</Heading>
        <Text fontSize="xs" color="blue.300">{t('settings.topics.sectionNote')}</Text>
        <Text fontSize="xs" color="whiteAlpha.600">{t('settings.topics.sectionDesc')}</Text>

        {loadError && (
          <Text fontSize="sm" color="red.300">{loadError}</Text>
        )}

        {topics && (
          <>
            <HStack align="flex-end">
              <Box flex="1">
                <InputField
                  label={t('settings.topics.listLabel')}
                  value={newTopicDraft}
                  onChange={setNewTopicDraft}
                  placeholder={t('settings.topics.listPlaceholder')}
                />
              </Box>
              <Button
                size="xs"
                tone="blue"
                onClick={() => handleAddTopic()}
                loading={savingTopics}
                disabled={!newTopicDraft.trim() || atMax}
              >
                {t('settings.topics.add')}
              </Button>
            </HStack>
            <Text fontSize="xs" color="whiteAlpha.600">{t('settings.topics.listHelp')}</Text>
            {atMax && (
              <Text fontSize="xs" color="orange.300">
                {t('settings.topics.tooMany', { max: MAX_TOPICS })}
              </Text>
            )}

            {topics.topics.length === 0 ? (
              <Text fontSize="sm" color="whiteAlpha.600">{t('settings.topics.empty')}</Text>
            ) : (
              <Stack gap={1}>
                {topics.topics.map((topic) => (
                  <HStack key={topic} justify="space-between">
                    <Text fontSize="sm">{topic}</Text>
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => handleRemoveTopic(topic)}
                      disabled={savingTopics}
                    >
                      {t('settings.topics.remove')}
                    </Button>
                  </HStack>
                ))}
              </Stack>
            )}

            {topics.suggestions.length > 0 && (
              <Stack gap={1}>
                <Text fontSize="xs" color="whiteAlpha.600">{t('settings.topics.suggestionsLabel')}</Text>
                <HStack flexWrap="wrap" gap={2}>
                  {topics.suggestions.map((suggestion) => (
                    <Button
                      key={suggestion}
                      size="xs"
                      variant="outline"
                      onClick={() => handleAddTopic(suggestion)}
                      disabled={atMax || savingTopics}
                    >
                      {suggestion}
                    </Button>
                  ))}
                </HStack>
              </Stack>
            )}

            <SwitchField
              label={t('settings.topics.newsToggle')}
              checked={topics.news.enabled}
              onChange={handleToggleNews}
              // 只在「還沒開啟」時擋，開著就永遠可以關掉。若無條件用 hasNoTopics
              // 停用，使用者先開新聞、再把話題刪光，開關就卡在 ON 拔不掉了。
              disabled={hasNoTopics && !topics.news.enabled}
            />
            <Text fontSize="xs" color="whiteAlpha.600">{t('settings.topics.newsToggleHelp')}</Text>
            <Text fontSize="xs" color="whiteAlpha.600">{t('settings.topics.newsExplainer')}</Text>
            {hasNoTopics && (
              <Text fontSize="xs" color="orange.300">{t('settings.topics.newsNeedsTopics')}</Text>
            )}

            {topics.news.enabled && (
              <Stack gap={2}>
                <NumberField
                  label={t('settings.topics.intervalHours')}
                  value={intervalDraft}
                  onChange={setIntervalDraft}
                  min={INTERVAL_HOURS_MIN}
                  max={INTERVAL_HOURS_MAX}
                  step={1}
                />
                <Text fontSize="xs" color="whiteAlpha.600">{t('settings.topics.intervalHoursHelp')}</Text>
                <HStack>
                  <Button
                    size="xs"
                    tone="blue"
                    onClick={handleIntervalSave}
                    loading={savingInterval}
                  >
                    {t('common.save')}
                  </Button>
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={handleRefreshNow}
                    loading={refreshing}
                    loadingText={t('settings.topics.refreshing')}
                    disabled={hasNoTopics}
                  >
                    {t('settings.topics.refreshNow')}
                  </Button>
                </HStack>
                <Text fontSize="xs" color="whiteAlpha.600">
                  {topics.last_news_refresh
                    ? t('settings.topics.lastRefresh', {
                      time: formatDistanceToNow(new Date(topics.last_news_refresh), { addSuffix: true }),
                    })
                    : t('settings.topics.neverRefreshed')}
                </Text>
              </Stack>
            )}
          </>
        )}
      </Stack>
    </Stack>
  );
}

export default Agent;
