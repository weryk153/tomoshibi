// 角色語音的播放音量（0.0–1.0）。
//
// 為什麼獨立成一個模組、而不是塞進 use-general-settings 的 settings 物件裡讓
// use-audio-task 從 context 讀：播放端是 handleAudioPlayback，它在
// audioTaskQueue 裡以 promise 佇列的形式跑，閉包在任務排進佇列的當下就固定了。
// 從 React state 讀會拿到「排進佇列時」的音量而不是「真的播出去時」的音量——
// 使用者在一輪回覆播到一半調整滑桿，剩下的句子仍會用舊值，而且畫面上沒有任何
// 線索。改成播放當下直接讀 localStorage，就沒有這個時間差。
//
// 讀取成本可以忽略：一段音訊只讀一次，不是每幀。
//
// 注意這裡只影響 HTMLAudioElement 的輸出音量，不影響嘴型。嘴型走的是
// model._wavFileHandler.start(audioDataUrl) 這條獨立管線，吃的是音訊資料本身的
// 振幅，不經過 audio.volume。所以把音量調小（甚至靜音）時嘴型照常會動——這是
// 想要的行為，不是漏掉的同步。
export const VOICE_VOLUME_KEY = 'appVoiceVolume';
export const DEFAULT_VOICE_VOLUME = 1.0;

export const MIN_VOICE_VOLUME = 0;

// 上限是 5.0（500%）而不是 1.0，因為 1.0 根本不夠大聲。
//
// 實測 cache/ 裡的 GPT-SoVITS 輸出：peak 落在 -17.6 ~ -23.8 dBFS、RMS 約 -35
// dBFS。也就是音量開到滿，訊號也只用掉滿刻度的 13%——正常語音大約是 peak
// -3 ~ -6 dBFS，這裡整整少了 18 dB。HTMLAudioElement 的 .volume 上限就是 1.0，
// 只能衰減不能放大，所以天花板卡死在「原本就很小聲」。
//
// 量到的最小餘裕是 7.56x（peak 0.132 那個檔案），5.0 仍在不削波的範圍內；
// 而且 voice-gain.ts 後面還串了一顆 limiter 擋住比這更大聲的意外輸入。
// 超過 1.0 的部分不能用 .volume 做，要走 Web Audio 的 GainNode，見 voice-gain.ts。
export const MAX_VOICE_VOLUME = 5;

/** 夾到 [0, MAX_VOICE_VOLUME]；非有限數（NaN／Infinity）一律退回預設值。 */
export function clampVoiceVolume(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_VOICE_VOLUME;
  return Math.min(MAX_VOICE_VOLUME, Math.max(MIN_VOICE_VOLUME, value));
}

/**
 * 讀出目前設定的語音音量。
 *
 * 沒存過、存了壞值、或 localStorage 整個不能用（Safari 無痕、SSR、測試環境）
 * 時一律回預設值——這條路徑在每段音訊播放前都會跑，絕不能往外拋。
 */
export function loadVoiceVolume(): number {
  try {
    const stored = globalThis.localStorage?.getItem(VOICE_VOLUME_KEY);
    // 空字串與 null 都當成沒設定過。注意不能用 `if (!stored)` 之後才 parse
    // 就算了事——'0' 是合法值且為 truthy 字串，這裡順序是對的，但改動時要留意。
    if (stored === null || stored === undefined || stored === '') {
      return DEFAULT_VOICE_VOLUME;
    }
    const parsed = Number.parseFloat(stored);
    if (Number.isNaN(parsed)) return DEFAULT_VOICE_VOLUME;
    return clampVoiceVolume(parsed);
  } catch {
    return DEFAULT_VOICE_VOLUME;
  }
}

/** 寫入語音音量（先夾值再存，壞值不會落地）。 */
export function saveVoiceVolume(value: number): void {
  try {
    globalThis.localStorage?.setItem(VOICE_VOLUME_KEY, String(clampVoiceVolume(value)));
  } catch {
    // 寫不進去就算了：音量是偏好設定，不值得為它中斷任何流程。
  }
}
