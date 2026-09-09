import assert from "node:assert/strict";
import test from "node:test";
import { AudioManager } from "./audio-manager.ts";
import { registerRenderer, type CharacterRenderer } from "../avatar/character-renderer.ts";

function fakeAudio() {
  const calls: string[] = [];
  return {
    calls,
    src: "data:x",
    pause() { calls.push("pause"); },
    load() { calls.push("load"); },
  } as unknown as HTMLAudioElement & { calls: string[] };
}

test("beginSpeaking 一個 stop 週期內只回一次 true", () => {
  const m = new AudioManager();
  assert.equal(m.beginSpeaking(), true);
  assert.equal(m.beginSpeaking(), false);
  m.stopCurrentAudioAndLipSync();
  assert.equal(m.beginSpeaking(), true);
});

test("stop 會停音訊、叫 renderer.stop、且 settle 只叫一次", () => {
  const m = new AudioManager();
  const audio = fakeAudio();
  let stopped = 0;
  let settled = 0;
  const r: CharacterRenderer = {
    beginSegment() {},
    stop() { stopped += 1; },
    resetExpression() {},
  };
  const unregister = registerRenderer(r);
  m.setCurrentAudio(audio, () => { settled += 1; });
  m.stopCurrentAudioAndLipSync();
  m.stopCurrentAudioAndLipSync();
  unregister();
  assert.deepEqual(audio.calls, ["pause", "load"]);
  assert.equal(audio.src, "");
  assert.equal(stopped, 2);
  assert.equal(settled, 1);
  assert.equal(m.hasCurrentAudio(), false);
});

test("renderer.stop 丟例外不會讓 settle 漏掉", () => {
  const m = new AudioManager();
  const r: CharacterRenderer = {
    beginSegment() {},
    stop() { throw new Error("boom"); },
    resetExpression() {},
  };
  const unregister = registerRenderer(r);
  let settled = 0;
  m.setCurrentAudio(fakeAudio(), () => { settled += 1; });
  m.stopCurrentAudioAndLipSync();
  unregister();
  assert.equal(settled, 1);
});

test("自然結束的 clearCurrentAudio 之後，stop 不再 settle", () => {
  const m = new AudioManager();
  const audio = fakeAudio();
  let settled = 0;
  m.setCurrentAudio(audio, () => { settled += 1; });
  m.clearCurrentAudio(audio);
  m.stopCurrentAudioAndLipSync();
  assert.equal(settled, 0);
});
