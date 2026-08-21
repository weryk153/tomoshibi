// 超過 100% 的語音放大。
//
// HTMLAudioElement 的 .volume 只吃 [0, 1]，只能衰減不能放大，而 GPT-SoVITS 的
// 輸出實測 RMS 只有 -35 dBFS（見 voice-volume.ts 的說明），所以「開到滿還是太
// 小聲」是必然的。要再大聲只能把訊號送進 Web Audio 的 GainNode。
//
// 訊號鏈：MediaElementSource → GainNode(gain>1) → DynamicsCompressor(limiter)
//                            → destination
//
// limiter 不是可有可無的裝飾：允許到 5x 之後，遇到比實測樣本更大聲的輸出就會
// 直接數位削波，那個聲音是刺耳的破音而不是「有點大聲」。壓在 -1.5 dBFS、
// ratio 20:1、attack 3ms，效果是「再大也不會破」，代價是極大聲的瞬間會被壓扁
// 一點——這個交換對語音來說完全划算。
//
// 最重要的安全性質：**寧可小聲，絕不無聲**。
// createMediaElementSource() 一旦呼叫，該元素的聲音就只會從這條 graph 出去，
// 不再直接送到喇叭。如果那時 AudioContext 還是 suspended（瀏覽器的自動播放
// 政策，使用者還沒跟頁面互動過），使用者會聽到「完全沒有聲音」——比太小聲糟
// 得多。所以下面每一個不確定的分支都在「還沒接上去」之前就 return null，讓
// 呼叫端退回原本的 audio.volume 路徑。

let sharedContext: AudioContext | null = null;

/** 取得共用的 AudioContext；不支援或建立失敗時回 null。 */
function getSharedContext(): AudioContext | null {
  if (sharedContext) return sharedContext;
  try {
    const Ctor = (globalThis as any).AudioContext
      ?? (globalThis as any).webkitAudioContext;
    if (!Ctor) return null;
    sharedContext = new Ctor();
    return sharedContext;
  } catch {
    // 瀏覽器可能因為 context 數量上限而拒絕；這不該中斷播放。
    return null;
  }
}

export interface VoiceGainHandle {
  /** 播放結束時呼叫，釋放這段音訊建立的節點。 */
  disconnect(): void;
}

/**
 * 把 audio 元素接上放大鏈。
 *
 * 回傳 null 代表「沒有接上，請照原本的方式播放」——gain <= 1、瀏覽器不支援
 * Web Audio、AudioContext 尚未 running、或建立節點失敗都算。呼叫端看到 null
 * 時必須自己設 audio.volume。
 */
// 每個元素的音訊圖只能建一次（createMediaElementSource 的硬限制），而現在整個
// app 共用同一個 <audio>，所以建好之後要留著反覆使用。用 WeakMap 是為了元素真的
// 被丟棄時不會把節點一起留住。
const graphs = new WeakMap<HTMLAudioElement, { gain: GainNode }>();

export function attachVoiceGain(
  audio: HTMLAudioElement,
  gain: number,
): VoiceGainHandle | null {
  const wanted = Number.isFinite(gain) && gain > 1 ? gain : 1;

  // 這個元素已經接上過了：只要改增益值，不能也不需要重建。
  //
  // wanted <= 1 時仍然要把增益歸位成 1 再回 null——元素一旦接進音訊圖，聲音就
  // 只從這條路出去了，留著上一段的放大值會讓這一段莫名其妙變大聲。回 null 讓
  // 呼叫端照常用 audio.volume 衰減，那個在音訊圖之前生效，兩者不衝突。
  const existing = graphs.get(audio);
  if (existing) {
    existing.gain.gain.value = wanted;
    if (wanted <= 1) return null;
    return {
      disconnect(): void {
        // 不拆節點——拆了下一段就沒得用，而且來源無法重建。歸位就好。
        existing.gain.gain.value = 1;
      },
    };
  }

  // 還沒接過，而且這段不需要放大：先不要接。接上去是不可逆的，沒必要就別做。
  if (wanted <= 1) return null;

  const ctx = getSharedContext();
  if (!ctx) return null;

  // suspended 時先試著喚醒，但 resume() 是非同步的，這一句不會馬上變 running。
  // 所以本段音訊仍然放棄放大（回 null → 呼叫端用 .volume 正常播放），等下一段
  // 音訊時 context 通常已經 running。第一句略小聲，好過第一句完全沒聲音。
  if (ctx.state === 'suspended') {
    ctx.resume().catch(() => {});
    return null;
  }
  if (ctx.state !== 'running') return null;

  try {
    const source = ctx.createMediaElementSource(audio);
    const gainNode = ctx.createGain();
    gainNode.gain.value = wanted;

    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -1.5;
    limiter.knee.value = 0;
    limiter.ratio.value = 20;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.25;

    source.connect(gainNode);
    gainNode.connect(limiter);
    limiter.connect(ctx.destination);

    graphs.set(audio, { gain: gainNode });

    return {
      disconnect(): void {
        gainNode.gain.value = 1;
      },
    };
  } catch {
    // 接不上就退回一般播放，不能讓一個音效問題炸掉整輪對話。
    return null;
  }
}

/** 測試用：清掉共用 context，讓下一次呼叫重新建立。 */
export function resetVoiceGainForTest(): void {
  sharedContext = null;
}


/**
 * 趁使用者手勢喚醒共用的 AudioContext。
 *
 * 這個 context 是延遲建立的（第一次需要放大音量時才建）。在 iOS 上它建立出來就是
 * suspended，而喚醒必須發生在使用者手勢裡，否則 resume() 不會生效。audio-unlock
 * 在首次手勢時呼叫這裡，順便把它建好並喚醒——不然第一段語音永遠拿不到放大。
 */
export function resumeSharedAudioContext(): void {
  const ctx = getSharedContext();
  if (ctx && ctx.state === 'suspended') {
    ctx.resume().catch(() => {});
  }
}
