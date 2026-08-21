/**
 * Global audio manager for handling audio playback and interruption
 * This ensures all components share the same audio reference
 */
export class AudioManager {
  private currentAudio: HTMLAudioElement | null = null;
  private currentModel: any | null = null;
  private speakingModel: any | null = null;
  // 目前這段音訊所屬播放 task 的收尾函式。播放 task 的 promise 平常靠 audio 的
  // ended／error 事件 resolve，但被這裡停掉的音訊（pause + 清空 src + load）
  // 那些事件一個都不會來，promise 就永遠懸著，音訊佇列跟著卡死——最後整輪對話
  // 收不了尾。所以停止必須自己把 task 結掉，不能指望瀏覽器補一個事件。
  private currentSettle: (() => void) | null = null;

  /**
   * Mark a model as speaking.
   * Returns true only for the first chunk of a continuous response so the Talk
   * motion is not restarted at every synthesized audio chunk.
   */
  beginSpeaking(model: any): boolean {
    const shouldStartTalkMotion = this.speakingModel !== model;
    this.speakingModel = model;
    this.currentModel = model;
    return shouldStartTalkMotion;
  }

  /**
   * Set the current playing audio.
   *
   * onStopped 由播放 task 傳入，讓 stopCurrentAudioAndLipSync() 能確實地結束
   * 那個 task。省略時行為與以往相同（只有事件能收尾），所以呼叫端沒改到也不會壞。
   */
  setCurrentAudio(audio: HTMLAudioElement, model: any, onStopped?: () => void) {
    this.currentAudio = audio;
    this.currentModel = model;
    this.currentSettle = onStopped ?? null;
  }

  /**
   * Stop current audio playback and lip sync
   */
  stopCurrentAudioAndLipSync() {
    const audio = this.currentAudio;
    const model = this.speakingModel ?? this.currentModel;
    // 先取走再清空：收尾函式在最後才呼叫（此時狀態已重設完畢），而且只會被
    // 呼叫一次——重複停止不該重複收尾。
    const settle = this.currentSettle;
    this.currentSettle = null;

    if (audio) {
      console.log('[AudioManager] Stopping current audio');

      // Stop audio playback
      audio.pause();
      audio.src = '';
      audio.load();
    }

    // Stop Live2D lip sync even when the final chunk already ended naturally.
    if (model && model._wavFileHandler) {
      try {
        model._wavFileHandler.releasePcmData();
        console.log('[AudioManager] Called _wavFileHandler.releasePcmData()');

        model._wavFileHandler._lastRms = 0.0;
        model._wavFileHandler._sampleOffset = 0;
        model._wavFileHandler._userTimeSeconds = 0.0;
        if (typeof model._smoothedLipSyncValue === 'number') {
          model._smoothedLipSyncValue = 0.0;
        }
      } catch (e) {
        console.error('[AudioManager] Error stopping/resetting wavFileHandler:', e);
      }
    }

    // Starting Idle through Cubism's motion manager crossfades the looping Talk
    // motion instead of leaving it active or stopping it abruptly.
    if (model) {
      try {
        if (typeof model.returnToIdleMotion === 'function') {
          model.returnToIdleMotion();
        } else if (typeof model.startRandomMotion === 'function') {
          model.startRandomMotion('Idle', 3);
        }
      } catch (e) {
        console.error('[AudioManager] Error returning model to idle:', e);
      }
    }

    this.currentAudio = null;
    this.currentModel = null;
    this.speakingModel = null;

    if (settle) settle();
  }

  /**
   * Clear the current audio reference (called when audio ends naturally)
   */
  clearCurrentAudio(audio: HTMLAudioElement) {
    if (this.currentAudio === audio) {
      this.currentAudio = null;
      // 自然結束的 task 已經自己 resolve 過了，解除註冊，之後的停止就不會
      // 再收尾它一次。
      this.currentSettle = null;
    }
  }

  /**
   * Check if there's currently playing audio
   */
  hasCurrentAudio(): boolean {
    return this.currentAudio !== null;
  }
}

// Export singleton instance
export const audioManager = new AudioManager();
