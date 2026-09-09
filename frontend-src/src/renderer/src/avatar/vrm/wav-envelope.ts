// VRM 口型的資料來源：把 base64 WAV 解成 PCM，算成「每 20ms 一個值」的音量包絡，
// 播放時用 audio.currentTime 查。跟 Cubism 的 _wavFileHandler 同一個思路。
//
// 不走 Web Audio AnalyserNode 的理由：那要 AudioContext 醒著、而且要把共用的
// <audio> 接進音訊圖——voice-gain.ts 已經說明那一步不可逆、context 還 suspended
// 時接了會完全無聲。這裡純算數，跟播放路徑零互動。
//
// 每一段用自己的峰值正規化：GPT-SoVITS 輸出實測 -35 dBFS，不正規化的話 sigmoid
// 整形後永遠低於門檻，嘴巴不會開。

export interface WavEnvelope {
  values: Float32Array;
  frameSeconds: number;
}

// 假包絡的常數。Float32Array 存不下精確的 0.35，所以 envelopeAt 對這個物件直接回這個數。
export const FAKE_MOUTH_VALUE = 0.35;

/** 標頭壞掉時的退路：嘴巴微開的常數，讓「在講話」看得出來。 */
export const FAKE_ENVELOPE: WavEnvelope = {
  values: new Float32Array([FAKE_MOUTH_VALUE]),
  frameSeconds: Number.POSITIVE_INFINITY,
};

export interface PcmData {
  sampleRate: number;
  channels: number;
  samples: Int16Array;
}

function tag(view: DataView, offset: number): string {
  return String.fromCharCode(
    view.getUint8(offset),
    view.getUint8(offset + 1),
    view.getUint8(offset + 2),
    view.getUint8(offset + 3),
  );
}

/** RIFF/WAVE、PCM16。找 fmt 與 data chunk；其他格式回 null。 */
export function parseWavPcm16(buf: ArrayBuffer): PcmData | null {
  if (buf.byteLength < 12) return null;
  const view = new DataView(buf);
  if (tag(view, 0) !== "RIFF" || tag(view, 8) !== "WAVE") return null;

  let offset = 12;
  let sampleRate = 0;
  let channels = 0;
  let bits = 0;
  let format = 0;
  while (offset + 8 <= buf.byteLength) {
    const id = tag(view, offset);
    const size = view.getUint32(offset + 4, true);
    const body = offset + 8;
    if (id === "fmt ") {
      if (body + 16 > buf.byteLength) return null;
      format = view.getUint16(body, true);
      channels = view.getUint16(body + 2, true);
      sampleRate = view.getUint32(body + 4, true);
      bits = view.getUint16(body + 14, true);
    } else if (id === "data") {
      if (format !== 1 || bits !== 16 || channels < 1 || sampleRate < 1) return null;
      const end = Math.min(buf.byteLength, body + size);
      const count = Math.floor((end - body) / 2);
      // 複製一份，避免 data 的 offset 不是 2 的倍數時 Int16Array 建構失敗。
      const samples = new Int16Array(count);
      for (let i = 0; i < count; i++) samples[i] = view.getInt16(body + i * 2, true);
      return { sampleRate, channels, samples };
    }
    offset = body + size + (size % 2);
  }
  return null;
}

/** 每幀取 |樣本| 最大值（跨聲道），整段以峰值正規化到 0..1。 */
export function computeEnvelope(pcm: PcmData, frameSeconds = 0.02): WavEnvelope {
  const perFrame = Math.max(1, Math.round(pcm.sampleRate * frameSeconds)) * pcm.channels;
  const frames = Math.ceil(pcm.samples.length / perFrame);
  const values = new Float32Array(frames);
  let peak = 0;
  for (let f = 0; f < frames; f++) {
    let m = 0;
    const start = f * perFrame;
    const end = Math.min(pcm.samples.length, start + perFrame);
    for (let i = start; i < end; i++) {
      const a = Math.abs(pcm.samples[i]);
      if (a > m) m = a;
    }
    values[f] = m;
    if (m > peak) peak = m;
  }
  if (peak > 0) for (let f = 0; f < frames; f++) values[f] /= peak;
  return { values, frameSeconds };
}

export function envelopeAt(env: WavEnvelope, t: number): number {
  if (t < 0) return 0;
  if (env === FAKE_ENVELOPE) return FAKE_MOUTH_VALUE;
  const i = Math.floor(t / env.frameSeconds);
  return i < env.values.length ? env.values[i] : 0;
}

/** ChatVRM 的整形曲線：把 0..1 的音量壓成有開有合的嘴型。 */
export function shapeMouth(v: number): number {
  const s = 1 / (1 + Math.exp(-45 * v + 5));
  return s < 0.1 ? 0 : s;
}

function decodeBase64(b64: string): ArrayBuffer | null {
  try {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out.buffer;
  } catch {
    return null;
  }
}

export function envelopeFromDataUrl(dataUrl: string): WavEnvelope | null {
  const comma = dataUrl.indexOf(",");
  if (comma < 0) return null;
  const buf = decodeBase64(dataUrl.slice(comma + 1));
  if (!buf) return null;
  const pcm = parseWavPcm16(buf);
  return pcm ? computeEnvelope(pcm) : null;
}
