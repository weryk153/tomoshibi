/* eslint-disable func-names */
/* eslint-disable no-underscore-dangle */
/* eslint-disable @typescript-eslint/ban-ts-comment */
import { useRef, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAiState } from '@/context/ai-state-context';
import { useSubtitle } from '@/context/subtitle-context';
import { useChatHistory } from '@/context/chat-history-context';
import { audioTaskQueue } from '@/utils/task-queue';
import { audioManager } from '@/utils/audio-manager';
import { loadVoiceVolume } from '@/utils/voice-volume';
import { getSharedAudio } from '@/utils/shared-audio';
import { attachVoiceGain } from '@/utils/voice-gain';
import { toaster } from '@/components/ui/tw/toaster';
import { classifyMediaError } from '@/utils/media-error';
import { useWebSocket } from '@/context/websocket-context';
import { DisplayText } from '@/services/websocket-service';
import { getActiveRenderer } from '@/avatar/character-renderer';
import type { MotionRequest } from '@/avatar/character-renderer';

interface AudioTaskOptions {
  audioBase64: string
  volumes: number[]
  sliceLength: number
  displayText?: DisplayText | null
  subtitleText?: string
  expressions?: string[] | number[] | null
  expressionIntensities?: number[] | null
  motions?: MotionRequest[] | null
  speaker_uid?: string
  forwarded?: boolean
}

/**
 * Custom hook for handling audio playback tasks with Live2D lip sync
 */
// 共用音訊元素的播放序號。元素只有一個，所以「這是不是同一段」不能再靠元素
// 身分判斷——晚到的 cleanup 會把新的那段清掉。
let playGeneration = 0;

export const useAudioTask = () => {
  const { t } = useTranslation();
  const { aiState, backendSynthComplete, setBackendSynthComplete } = useAiState();
  const { setSubtitleText } = useSubtitle();
  const { appendResponse, appendAIMessage } = useChatHistory();
  const { sendMessage } = useWebSocket();

  // State refs to avoid stale closures
  const stateRef = useRef({
    aiState,
    setSubtitleText,
    appendResponse,
    appendAIMessage,
  });

  // Note: currentAudioRef and currentModelRef are now managed by the global audioManager

  stateRef.current = {
    aiState,
    setSubtitleText,
    appendResponse,
    appendAIMessage,
  };

  /**
   * Stop current audio playback and lip sync (delegates to global audioManager)
   */
  const stopCurrentAudioAndLipSync = useCallback(() => {
    audioManager.stopCurrentAudioAndLipSync();
  }, []);

  /**
   * Handle audio playback with Live2D lip sync
   */
  const handleAudioPlayback = (options: AudioTaskOptions): Promise<void> => new Promise((resolve) => {
    const {
      aiState: currentAiState,
      setSubtitleText: updateSubtitle,
      appendResponse: appendText,
      appendAIMessage: appendAI,
    } = stateRef.current;

    // Skip if already interrupted
    if (currentAiState === 'interrupted') {
      console.warn('Audio playback blocked by interruption state.');
      resolve();
      return;
    }

    const {
      audioBase64, displayText, subtitleText, expressions, expressionIntensities, motions, forwarded,
    } = options;

    // Update display text
    if (displayText) {
      const visibleText = subtitleText || displayText.text;
      // Keep the canonical Japanese text for interruption/context bookkeeping,
      // but use the translated subtitle for every user-visible text surface.
      appendText(displayText.text);
      appendAI(visibleText, displayText.name, displayText.avatar);
      if (audioBase64) {
        updateSubtitle(visibleText);
      }
      if (!forwarded) {
        sendMessage({
          type: "audio-play-start",
          display_text: displayText,
          subtitle_text: subtitleText,
          forwarded: true,
        });
      }
    }

    try {
      // Process audio if available
      if (audioBase64) {
        const audioDataUrl = `data:audio/wav;base64,${audioBase64}`;

        // 共用同一個 <audio>，不是每段各建一個。iOS 的自動播放授權掛在元素上，
        // new Audio() 出來的都是未授權的新元素，程式主動 play() 一律被擋——實測
        // 在首次手勢解鎖後，桌面正常但 iPad 照樣沒聲音。詳見 utils/shared-audio.ts。
        //
        // 換 src 就等於換下一段。設 src 會自動中止上一段的播放，佇列本來就是
        // 序列化的，不會有兩段同時在播。
        const audio = getSharedAudio();
        audio.src = audioDataUrl;

        // 這一次播放的識別。元素是共用的，所以 audioManager 靠元素身分做的
        // 「這是不是同一段」判斷全部失效——晚到的 cleanup 會把新的那段清掉。
        // 用遞增的號碼取代身分比對。
        playGeneration += 1;
        const myGeneration = playGeneration;

        // 監聽器不能累積：同一個元素播一百段就會掛上一百組 ended/error。
        // 用 AbortController 在 cleanup 時一次拆掉這一段掛上的全部。
        const listeners = new AbortController();

        // 播放當下才讀，不從 React state 拿——這個閉包在任務排進 audioTaskQueue
        // 的當下就固定了，用 state 會讓「播到一半調音量」對佇列裡剩下的句子無效。
        // 詳見 utils/voice-volume.ts 檔頭。
        const voiceVolume = loadVoiceVolume();

        // 超過 100% 要走 Web Audio 的 GainNode（.volume 上限就是 1.0，只能衰減
        // 不能放大）。attachVoiceGain 接不上時回 null——不支援、AudioContext 還
        // 沒被使用者手勢喚醒、建立節點失敗都算——這時退回一般的 .volume 路徑，
        // 結果是「比較小聲」而不是「沒有聲音」，見 voice-gain.ts 檔頭。
        const gainHandle = attachVoiceGain(audio, voiceVolume);
        audio.volume = gainHandle ? 1 : Math.min(1, voiceVolume);

        let isFinished = false;

        const cleanup = () => {
          listeners.abort();
          gainHandle?.disconnect();
          // 只有仍然是「當前這一段」時才去清 audioManager。晚到的 cleanup
          // （上一段的 ended 慢了一步）不可以把新的那段註銷掉。
          if (myGeneration === playGeneration) {
            audioManager.clearCurrentAudio(audio);
          }
          if (!isFinished) {
            isFinished = true;
            resolve();
          }
        };

        // cleanup 交給 audioManager，讓「從外部停掉這段音訊」也算一種收尾。
        // 少了這個，被停掉的音訊不會再發出 ended／error，這個 promise 就永遠
        // 懸著，整條音訊佇列卡死，最後整輪對話收不了尾（見 audio-manager.ts
        // 的 currentSettle 說明）。cleanup 自己有 isFinished 擋重入。
        audioManager.setCurrentAudio(audio, cleanup);

        audio.addEventListener('canplaythrough', () => {
          // Check for interruption before playback
          if (stateRef.current.aiState === 'interrupted' || !audioManager.hasCurrentAudio()) {
            console.warn('Audio playback cancelled due to interruption or audio was stopped');
            cleanup();
            return;
          }

          console.log('Starting audio playback with lip sync');
          audio.play().catch((err) => {
            console.error("Audio play error:", err);
            // 瀏覽器在使用者還沒跟頁面互動過之前會擋掉自動播放，play() 就以
            // NotAllowedError 被拒。先前這裡只有 console.error——角色照樣顯示
            // 字幕、嘴型也會動，但完全沒有聲音，而且畫面上沒有任何線索。在
            // 瀏覽器開前台時這是必然會遇到的第一個狀況。
            if (classifyMediaError(err) === 'denied') {
              toaster.create({
                // 固定 id：一輪回覆有很多句，每句都被擋的話不該疊出一整排
                // 一模一樣的提示。
                id: 'audio-autoplay-blocked',
                title: t('error.audioBlocked'),
                type: 'warning',
                duration: 8000,
              });
            }
            cleanup();
          });

          // renderer 在播放當下才讀（任務排進佇列時它可能還沒到或已經換掉）。
          // 沒有 renderer 就只是沒口型——音訊照播、字幕照出。以前這裡找不到
          // Live2D manager 會把整句丟掉；雙 renderer 之後每次切角色都有一段
          // 空窗，丟句子會變常態，所以改成降級而不是跳過。
          const renderer = getActiveRenderer();
          if (!renderer) {
            console.warn('[AudioTask] No character renderer registered; playing audio without lip sync');
            return;
          }
          const first = audioManager.beginSpeaking();
          try {
            renderer.beginSegment(
              audio,
              {
                expression: expressions?.[0],
                // 跟 expression 取同一個索引；沒給就是最滿。
                intensity: expressionIntensities?.[0],
                motion: motions?.[0] ?? undefined,
              },
              first,
            );
          } catch (e) {
            console.error('[AudioTask] renderer.beginSegment failed:', e);
          }
        }, { once: true, signal: listeners.signal });

        audio.addEventListener('ended', () => {
          console.log("Audio playback completed");
          cleanup();
        }, { signal: listeners.signal });

        audio.addEventListener('error', (error) => {
          console.error("Audio playback error:", error);
          cleanup();
        }, { signal: listeners.signal });

        audio.load();
      } else {
        resolve();
      }
    } catch (error) {
      console.error('Audio playback setup error:', error);
      audioManager.stopCurrentAudioAndLipSync();
      toaster.create({
        title: `${t('error.audioPlayback')}: ${error}`,
        type: "error",
        duration: 2000,
      });
      resolve();
    }
  });

  // Handle backend synthesis completion
  //
  // 一輪合成只該回報一次。這個 effect 的依賴裡有好幾個會在 render 之間換身分的
  // 函式，所以它會被重跑很多次；而 setBackendSynthComplete(false) 要等下一次
  // render 才生效，於是「還沒轉 false」的空窗期內每一個重跑都會通過舊的布林
  // 檢查各送一則。佇列剛好是空的時候（例如使用者打斷，佇列被清掉）
  // waitForCompletion() 立刻 resolve，這些重跑就會在同一瞬間連珠炮送出——實測
  // 抓到過一次連送 10 則。
  //
  // 這不只是吵：那些多送的回報全部落在後端還沒開始等的時間點，被直接丟掉，而
  // 旗標已經被它們清成 false，等到真正播完時就再也沒有人會送了。後端於是永遠
  // 等不到 frontend-playback-complete。用 ref 上閂，一輪只放行一則。
  const playbackCompleteSentRef = useRef(false);

  useEffect(() => {
    if (!backendSynthComplete) {
      playbackCompleteSentRef.current = false;
      return undefined;
    }

    let cancelled = false;

    const handleComplete = async () => {
      await audioTaskQueue.waitForCompletion();
      if (cancelled || playbackCompleteSentRef.current) return;
      playbackCompleteSentRef.current = true;

      stopCurrentAudioAndLipSync();
      sendMessage({ type: "frontend-playback-complete" });
      setBackendSynthComplete(false);
    };

    handleComplete();

    return () => {
      cancelled = true;
    };
  }, [backendSynthComplete, sendMessage, setBackendSynthComplete, stopCurrentAudioAndLipSync]);

  /**
   * Add a new audio task to the queue
   */
  const addAudioTask = async (options: AudioTaskOptions) => {
    const { aiState: currentState } = stateRef.current;

    if (currentState === 'interrupted') {
      console.log('Skipping audio task due to interrupted state');
      return;
    }

    console.log(`Adding audio task ${options.displayText?.text} to queue`);
    audioTaskQueue.addTask(() => handleAudioPlayback(options));
  };

  return {
    addAudioTask,
    appendResponse,
    stopCurrentAudioAndLipSync,
  };
};
