import assert from "node:assert/strict";
import test from "node:test";
import {
  computeEnvelope,
  envelopeAt,
  envelopeFromDataUrl,
  FAKE_ENVELOPE,
  parseWavPcm16,
  shapeMouth,
} from "./wav-envelope.ts";

/** 組一個 PCM16 WAV。channels 交錯，samples 是單聲道值、每聲道複製。 */
function wav(samples: number[], sampleRate = 16000, channels = 1): ArrayBuffer {
  const dataBytes = samples.length * channels * 2;
  const buf = new ArrayBuffer(44 + dataBytes);
  const v = new DataView(buf);
  const str = (o: number, s: string) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  str(0, "RIFF"); v.setUint32(4, 36 + dataBytes, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, channels, true); v.setUint32(24, sampleRate, true);
  v.setUint32(28, sampleRate * channels * 2, true); v.setUint16(32, channels * 2, true);
  v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, dataBytes, true);
  let o = 44;
  for (const s of samples) for (let c = 0; c < channels; c++) { v.setInt16(o, s, true); o += 2; }
  return buf;
}

test("parseWavPcm16 讀出取樣率、聲道與樣本", () => {
  const p = parseWavPcm16(wav([0, 1000, -1000], 24000, 2));
  assert.ok(p);
  assert.equal(p.sampleRate, 24000);
  assert.equal(p.channels, 2);
  assert.equal(p.samples.length, 6);
});

test("壞標頭回 null", () => {
  assert.equal(parseWavPcm16(new ArrayBuffer(10)), null);
  const b = wav([0]); new DataView(b).setUint16(20, 3, true); // float 格式
  assert.equal(parseWavPcm16(b), null);
});

test("包絡：靜音全零、峰值落在正確的幀、整段以峰值正規化", () => {
  // 16kHz、20ms 一幀 = 320 樣本。第 2 幀放一個小訊號、第 4 幀放大訊號。
  const s = new Array(320 * 5).fill(0);
  s[320 * 1 + 10] = 300;
  s[320 * 3 + 10] = 3000;
  const env = computeEnvelope(parseWavPcm16(wav(s))!, 0.02);
  assert.equal(env.values.length, 5);
  assert.equal(env.values[0], 0);
  assert.ok(Math.abs(env.values[1] - 0.1) < 1e-6);
  assert.equal(env.values[3], 1);
  assert.equal(env.frameSeconds, 0.02);
});

test("全靜音不會除以零", () => {
  const env = computeEnvelope(parseWavPcm16(wav(new Array(640).fill(0)))!, 0.02);
  assert.deepEqual(Array.from(env.values), [0, 0]);
});

test("envelopeAt 依時間查幀，超界回 0", () => {
  const env = { values: new Float32Array([0, 0.5, 1]), frameSeconds: 0.02 };
  assert.equal(envelopeAt(env, -1), 0);
  assert.equal(envelopeAt(env, 0.021), 0.5);
  assert.equal(envelopeAt(env, 0.05), 1);
  assert.equal(envelopeAt(env, 0.06), 0);
});

test("shapeMouth 是 sigmoid，低於 0.1 歸零", () => {
  assert.equal(shapeMouth(0), 0);
  assert.ok(shapeMouth(1) > 0.99);
  assert.ok(shapeMouth(0.111) > 0.1);
});

test("envelopeFromDataUrl 解 base64；壞資料回 null", () => {
  const b64 = Buffer.from(wav([0, 5000, 0, 0])).toString("base64");
  const env = envelopeFromDataUrl(`data:audio/wav;base64,${b64}`);
  assert.ok(env && env.values.length >= 1);
  assert.equal(envelopeFromDataUrl("data:audio/wav;base64,AAAA"), null);
});

test("假包絡永遠回常數", () => {
  assert.equal(envelopeAt(FAKE_ENVELOPE, 0), 0.35);
  assert.equal(envelopeAt(FAKE_ENVELOPE, 99), 0.35);
});
