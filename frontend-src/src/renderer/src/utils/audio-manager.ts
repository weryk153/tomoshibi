/**
 * Global audio manager for handling audio playback and interruption
 * This ensures all components share the same audio reference
 */
import { getActiveRenderer } from "../avatar/character-renderer.ts";

export class AudioManager {
  private currentAudio: HTMLAudioElement | null = null;
  // 這輪回覆是否已經開講。以前靠「speakingModel 是不是同一個模型」判斷，
  // 模型在一輪裡不會換，所以語意等於「上次 stop 之後第一次」——現在直接記這件事。
  private speaking = false;
  // 目前這段音訊所屬播放 task 的收尾函式。播放 task 的 promise 平常靠 audio 的
  // ended／error 事件 resolve，但被這裡停掉的音訊（pause + 清空 src + load）
  // 那些事件一個都不會來，promise 就永遠懸著，音訊佇列跟著卡死——最後整輪對話
  // 收不了尾。所以停止必須自己把 task 結掉，不能指望瀏覽器補一個事件。
  private currentSettle: (() => void) | null = null;

  /**
   * Returns true only for the first chunk of a continuous response so the Talk
   * motion is not restarted at every synthesized audio chunk.
   */
  beginSpeaking(): boolean {
    const first = !this.speaking;
    this.speaking = true;
    return first;
  }

  /**
   * Set the current playing audio.
   *
   * onStopped 由播放 task 傳入，讓 stopCurrentAudioAndLipSync() 能確實地結束
   * 那個 task。省略時行為與以往相同（只有事件能收尾），所以呼叫端沒改到也不會壞。
   */
  setCurrentAudio(audio: HTMLAudioElement, onStopped?: () => void) {
    this.currentAudio = audio;
    this.currentSettle = onStopped ?? null;
  }

  /**
   * Stop current audio playback and lip sync
   */
  stopCurrentAudioAndLipSync() {
    const audio = this.currentAudio;
    // 先取走再清空：收尾函式在最後才呼叫（此時狀態已重設完畢），而且只會被
    // 呼叫一次——重複停止不該重複收尾。
    const settle = this.currentSettle;
    this.currentSettle = null;

    if (audio) {
      console.log("[AudioManager] Stopping current audio");
      audio.pause();
      audio.src = "";
      audio.load();
    }

    // 不管音訊是不是已經自然結束都要叫：最後一段播完了、lipsync 與 Talk 動作
    // 還掛著，這裡是唯一會把它們收掉的地方。
    try {
      getActiveRenderer()?.stop();
    } catch (e) {
      console.error("[AudioManager] renderer.stop() failed:", e);
    }

    this.currentAudio = null;
    this.speaking = false;

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
