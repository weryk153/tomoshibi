/* eslint-disable no-sparse-arrays */
/* eslint-disable react-hooks/exhaustive-deps */
// eslint-disable-next-line object-curly-newline
import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { wsService, MessageEvent } from '@/services/websocket-service';
import {
  WebSocketContext, HistoryInfo, defaultWsUrl, defaultBaseUrl,
} from '@/context/websocket-context';
import { ModelInfo, useLive2DConfig } from '@/context/live2d-config-context';
import { useSubtitle } from '@/context/subtitle-context';
import { audioTaskQueue } from '@/utils/task-queue';
import { useAudioTask } from '@/hooks/utils/use-audio-task';
import { useBgUrl } from '@/context/bgurl-context';
import { useConfig } from '@/context/character-config-context';
import { useChatHistory } from '@/context/chat-history-context';
import { toaster } from '@/components/ui/tw/toaster';
import { useVAD } from '@/context/vad-context';
import { AiState, useAiState } from "@/context/ai-state-context";
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { useGroup } from '@/context/group-context';
import { useInterrupt } from '@/hooks/utils/use-interrupt';
import { useBrowser } from '@/context/browser-context';
import { useStageEffect } from '@/context/stage-effect-context';
import { isStageEffectId } from '@/effects/stage-effect';
import { useStagePerformance } from '@/context/stage-performance-context';
import type { StagePerformanceTrigger } from '@/effects/stage-performance';
import { shouldHonourStartMic } from '@/services/mic-mode';

function WebSocketHandler({ children }: { children: React.ReactNode }) {
  const { t } = useTranslation();
  const [wsState, setWsState] = useState<string>('CLOSED');
  const [wsUrl, setWsUrl] = useLocalStorage<string>('wsUrl', defaultWsUrl);
  const [baseUrl, setBaseUrl] = useLocalStorage<string>('baseUrl', defaultBaseUrl);
  const { aiState, setAiState, backendSynthComplete, setBackendSynthComplete } = useAiState();
  const { setModelInfo } = useLive2DConfig();
  const { setSubtitleText, clearSpeechSubtitle } = useSubtitle();
  const { clearResponse, setForceNewMessage, appendHumanMessage, appendOrUpdateToolCallMessage } = useChatHistory();
  const { addAudioTask } = useAudioTask();
  const bgUrlContext = useBgUrl();
  const { confUid, setConfName, setConfUid, setConfigFiles } = useConfig();
  const [pendingModelInfo, setPendingModelInfo] = useState<ModelInfo | undefined>(undefined);
  const { setSelfUid, setGroupMembers, setIsOwner } = useGroup();
  const {
    startMic, stopMic, autoStartMicOnConvEnd, micOn, autoStopMic, autoStartMicOn,
  } = useVAD();
  const autoStartMicOnConvEndRef = useRef(autoStartMicOnConvEnd);
  // 後端每次連上都送 start-mic，那是「我這邊準備好了」不是「請打開麥克風」。
  // 使用者的麥克風偏好只存在瀏覽器裡，後端不可能知道，所以要在這一側否決。
  // 用 ref 是因為 handleControlMessage 被 memo 住，直接讀狀態會讀到舊值。
  const micStateRef = useRef({
    micOn, autoStopMic, autoStartMicOn, autoStartMicOnConvEnd,
  });
  micStateRef.current = {
    micOn, autoStopMic, autoStartMicOn, autoStartMicOnConvEnd,
  };
  const { interrupt } = useInterrupt();
  const { setBrowserViewData } = useBrowser();
  const { playEffect } = useStageEffect();
  const { getPool, playTrigger } = useStagePerformance();
  const performanceHandledRef = useRef(false);
  const performanceTriggerRef = useRef<StagePerformanceTrigger>('conversation');
  const latestUserTextRef = useRef('');
  // 後端已經指定的那段對話。history-list 晚一步到，不能拿它蓋掉這個值。
  const activeHistoryUidRef = useRef<string | null>(null);

  useEffect(() => {
    autoStartMicOnConvEndRef.current = autoStartMicOnConvEnd;
  }, [autoStartMicOnConvEnd]);

  useEffect(() => {
    if (pendingModelInfo && confUid) {
      // Backend model dictionaries store the original Cubism scale.  The renderer
      // historically displays it at 2x; perform that conversion exactly once at
      // the backend boundary, not in the general state setter used by UI toggles.
      setModelInfo({
        ...pendingModelInfo,
        kScale: Number(pendingModelInfo.kScale || 0.5) * 2,
      });
      setPendingModelInfo(undefined);
    }
  }, [pendingModelInfo, setModelInfo, confUid]);

  const {
    setCurrentHistoryUid, setMessages, setHistoryList,
  } = useChatHistory();

  const handleControlMessage = useCallback((controlText: string) => {
    switch (controlText) {
      case 'start-mic':
        if (!shouldHonourStartMic(micStateRef.current)) {
          console.log('Ignoring start-mic: microphone mode is off');
          break;
        }
        console.log('Starting microphone...');
        startMic();
        break;
      case 'stop-mic':
        console.log('Stopping microphone...');
        stopMic();
        break;
      case 'conversation-chain-start':
        performanceHandledRef.current = false;
        setAiState('thinking-speaking');
        audioTaskQueue.clearQueue();
        clearResponse();
        break;
      case 'conversation-chain-end':
        audioTaskQueue.addTask(() => new Promise<void>((resolve) => {
          setAiState((currentState: AiState) => {
            if (currentState === 'thinking-speaking') {
              // Auto start mic if enabled
              if (autoStartMicOnConvEndRef.current) {
                startMic();
              }
              return 'idle';
            }
            return currentState;
          });
          // 字幕是語音的文字面：聲音沒了，字也該收掉。每段語音播放時會把自己
          // 那句貼上畫面，但先前沒有人在整輪結束時把最後一句拿下來，於是它會
          // 一直掛在畫面上，直到某一輪剛好覆蓋掉。轉場通知有自己的清除計時器，
          // 不歸這裡清——判定收在 subtitle-context 的 clearSpeechSubtitle。
          clearSpeechSubtitle();
          resolve();
        }));
        break;
      default:
        console.warn('Unknown control command:', controlText);
    }
  }, [setAiState, clearResponse, setForceNewMessage, startMic, stopMic]);

  const handleWebSocketMessage = useCallback((message: MessageEvent) => {
    console.log('Received message from server:', message);
    switch (message.type) {
      case 'control':
        if (message.text) {
          handleControlMessage(message.text);
        }
        break;
      case 'set-model-and-conf':
        setAiState('loading');
        if (message.conf_name) {
          setConfName(message.conf_name);
        }
        if (message.conf_uid) {
          setConfUid(message.conf_uid);
          console.log('confUid', message.conf_uid);
        }
        if (message.client_uid) {
          setSelfUid(message.client_uid);
        }
        setPendingModelInfo(message.model_info);
        // setModelInfo(message.model_info);
        // We don't know when the confRef in live2d-config-context will be updated, so we set a delay here for convenience
        if (message.model_info && !message.model_info.url.startsWith("http")) {
          const modelUrl = baseUrl + message.model_info.url;
          // eslint-disable-next-line no-param-reassign
          message.model_info.url = modelUrl;
        }

        setAiState('idle');
        break;
      case 'full-text':
        if (message.text || message.text_key) {
          // 後端只送英文字面值（"Thinking..."、"Connection established"），照
          // 原樣顯示的話中文介面上會冒出英文。text_key 是可翻譯的穩定代號；
          // 舊後端沒有這個欄位，就退回原本的 text。
          setSubtitleText(
            message.text_key
              ? t(`subtitle.${message.text_key}`, { defaultValue: message.text || '' })
              : (message.text as string),
          );
        }
        break;
      case 'config-files':
        if (message.configs) {
          setConfigFiles(message.configs);
        }
        break;
      case 'config-switched':
        setAiState('idle');
        setSubtitleText(t('notification.characterLoaded'), 4000);

        toaster.create({
          title: t('notification.characterSwitched'),
          type: 'success',
          duration: 2000,
        });

        // setModelInfo(undefined);

        wsService.sendMessage({ type: 'fetch-history-list' });
        wsService.sendMessage({ type: 'create-new-history' });
        break;
      case 'persona-switched':
        setAiState('idle');
        toaster.create({
          title: message.persona_name
            ? t('notification.personaSwitched', { name: message.persona_name })
            : t('notification.personaReset'),
          type: 'success',
          duration: 2000,
        });
        break;
      case 'stage-effect':
        if (isStageEffectId(message.effect)) {
          playEffect(message.effect, message.effect_options);
        } else {
          console.warn('Unknown stage effect:', message.effect);
        }
        break;
      case 'background-files':
        if (message.files) {
          bgUrlContext?.setBackgroundFiles(message.files);
        }
        break;
      case 'audio':
        if (aiState === 'interrupted' || aiState === 'listening') {
          console.log('Audio playback intercepted. Sentence:', message.display_text?.text);
        } else {
          if (!performanceHandledRef.current) {
            const requestedPresetId = message.actions?.stage_performance;
            const performanceTrigger = performanceTriggerRef.current;
            const directorMode = getPool(performanceTrigger).mode;
            if (requestedPresetId || directorMode !== 'ai') {
              playTrigger(
                performanceTrigger,
                {
                  text: [
                    latestUserTextRef.current,
                    message.display_text?.text || '',
                  ].filter(Boolean).join('\n'),
                },
                requestedPresetId,
              );
              performanceHandledRef.current = true;
            }
          }
          console.log("actions", message.actions);
          addAudioTask({
            audioBase64: message.audio || '',
            volumes: message.volumes || [],
            sliceLength: message.slice_length || 0,
            displayText: message.display_text || null,
            subtitleText: message.subtitle_text,
            expressions: message.actions?.expressions || null,
            expressionIntensities: message.actions?.expression_intensities || null,
            motions: message.actions?.motions || null,
            forwarded: message.forwarded || false,
          });
        }
        break;
      case 'conversation-context':
        performanceTriggerRef.current = message.performance_trigger || 'conversation';
        performanceHandledRef.current = false;
        latestUserTextRef.current = '';
        break;
      case 'history-data':
        if (message.messages) {
          setMessages(message.messages);
        }
        if (message.history_uid) {
          activeHistoryUidRef.current = message.history_uid;
          setCurrentHistoryUid(message.history_uid);
        }
        // 重整時後端會自己把上一段對話推回來。那不是使用者剛做的動作，
        // 跳「已載入歷史」等於每次開頁面都彈一次沒人要的通知。
        if (!message.restored) {
          toaster.create({
            title: t('notification.historyLoaded'),
            type: 'success',
            duration: 2000,
          });
        }
        break;
      case 'new-history-created':
        setAiState('idle');
        setSubtitleText(t('notification.newConversation'), 4000);
        // No need to open mic here
        if (message.history_uid) {
          activeHistoryUidRef.current = message.history_uid;
          setCurrentHistoryUid(message.history_uid);
          setMessages([]);
          const newHistory: HistoryInfo = {
            uid: message.history_uid,
            latest_message: null,
            timestamp: new Date().toISOString(),
          };
          setHistoryList((prev: HistoryInfo[]) => [newHistory, ...prev]);
          toaster.create({
            title: t('notification.newChatHistory'),
            type: 'success',
            duration: 2000,
          });
        }
        break;
      case 'history-deleted':
        if (message.success && message.history_uid === activeHistoryUidRef.current) {
          activeHistoryUidRef.current = null;
        }
        toaster.create({
          title: message.success
            ? t('notification.historyDeleteSuccess')
            : t('notification.historyDeleteFail'),
          type: message.success ? 'success' : 'error',
          duration: 2000,
        });
        break;
      case 'history-list':
        if (message.histories) {
          setHistoryList(message.histories);
          // 這份列表比後端還原的那段對話晚到。列表是照時間排的，直接取
          // histories[0] 會把還原好的 uid 蓋成「最新那筆」——使用者切到舊對話
          // 再重整就會對不上。只有在還沒有任何對話時才需要這個 fallback。
          if (!activeHistoryUidRef.current && message.histories.length > 0) {
            activeHistoryUidRef.current = message.histories[0].uid;
            setCurrentHistoryUid(message.histories[0].uid);
          }
        }
        break;
      case 'user-input-transcription':
        console.log('user-input-transcription: ', message.text);
        if (message.text) {
          latestUserTextRef.current = message.text;
          appendHumanMessage(message.text);
        }
        break;
      case 'error':
        toaster.create({
          title: message.message,
          type: 'error',
          duration: 2000,
        });
        break;
      case 'group-update':
        console.log('Received group-update:', message.members);
        if (message.members) {
          setGroupMembers(message.members);
        }
        if (message.is_owner !== undefined) {
          setIsOwner(message.is_owner);
        }
        break;
      case 'group-operation-result':
        toaster.create({
          title: message.message,
          type: message.success ? 'success' : 'error',
          duration: 2000,
        });
        break;
      case 'backend-synth-complete':
        setBackendSynthComplete(true);
        break;
      case 'stage-director-configured':
        console.log('Stage director candidates configured:', message.candidate_count || 0);
        break;
      // 後端送的是 {type:'control', text:'conversation-chain-end'}，所以正常情況
      // 走的是 handleControlMessage。這個裸 type 的分支留著是為了 proxy——但它
      // 原本自己實作了一份不一樣的邏輯：佇列還有東西在播就「什麼都不做」，而且
      // 之後沒有任何人會補做。那等於默默丟掉整輪對話的收尾，aiState 永遠停在
      // thinking-speaking，主動發言與自動開麥就此失效，畫面上不會有任何線索。
      // 直接轉給同一個處理器，兩條路徑不會再有第二種行為。
      case 'conversation-chain-end':
        handleControlMessage('conversation-chain-end');
        break;
      case 'force-new-message':
        setForceNewMessage(true);
        break;
      case 'interrupt-signal':
        // Handle forwarded interrupt
        interrupt(false); // do not send interrupt signal to server
        break;
      case 'tool_call_status':
        if (message.tool_id && message.tool_name && message.status) {
          // If there's browser view data included, store it in the browser context
          if (message.browser_view) {
            console.log('Browser view data received:', message.browser_view);
            setBrowserViewData(message.browser_view);
          }

          appendOrUpdateToolCallMessage({
            id: message.tool_id,
            type: 'tool_call_status',
            role: 'ai',
            tool_id: message.tool_id,
            tool_name: message.tool_name,
            name: message.name,
            status: message.status as ('running' | 'completed' | 'error'),
            content: message.content || '',
            timestamp: message.timestamp || new Date().toISOString(),
          });
        } else {
          console.warn('Received incomplete tool_call_status message:', message);
        }
        break;
      default:
        console.warn('Unknown message type:', message.type);
    }
  }, [aiState, addAudioTask, appendHumanMessage, baseUrl, bgUrlContext, setAiState, setConfName, setConfUid, setConfigFiles, setCurrentHistoryUid, setHistoryList, setMessages, setModelInfo, setSubtitleText, clearSpeechSubtitle, startMic, stopMic, setSelfUid, setGroupMembers, setIsOwner, backendSynthComplete, setBackendSynthComplete, clearResponse, handleControlMessage, appendOrUpdateToolCallMessage, interrupt, setBrowserViewData, playEffect, getPool, playTrigger, t]);

  useEffect(() => {
    wsService.connect(wsUrl);
  }, [wsUrl]);

  useEffect(() => {
    const stateSubscription = wsService.onStateChange(setWsState);
    const messageSubscription = wsService.onMessage(handleWebSocketMessage);
    return () => {
      stateSubscription.unsubscribe();
      messageSubscription.unsubscribe();
    };
  }, [wsUrl, handleWebSocketMessage]);

  const webSocketContextValue = useMemo(() => ({
    sendMessage: wsService.sendMessage.bind(wsService),
    wsState,
    reconnect: () => wsService.connect(wsUrl),
    wsUrl,
    setWsUrl,
    baseUrl,
    setBaseUrl,
  }), [wsState, wsUrl, baseUrl]);

  return (
    <WebSocketContext.Provider value={webSocketContextValue}>
      {children}
    </WebSocketContext.Provider>
  );
}

export default WebSocketHandler;
