import assert from "node:assert/strict";
import test from "node:test";
import {
  createEmptySceneStore,
  createScenePreset,
  CURRENT_BACKGROUND_SCENE_ID,
  getScenePresets,
  normalizeSceneStore,
} from "./scene.ts";

test("新安裝沿用既有背景，不會擅自切換場景", () => {
  assert.equal(
    createEmptySceneStore().activeSceneId,
    CURRENT_BACKGROUND_SCENE_ID,
  );
});

test("場景資料正規化限制數值並阻擋可執行 URL", () => {
  const normalized = normalizeSceneStore({
    version: 1,
    activeSceneId: "room",
    customScenes: [
      {
        ...createScenePreset("room", "model3d", "Room"),
        sourceUrl: "javascript:alert(1)",
        opacity: 9,
        transitionMs: -1,
        model: {
          ...createScenePreset("model").model,
          cameraFov: 999,
          backgroundColor: "red",
        },
      },
    ],
  });
  const room = normalized.customScenes[0];
  assert.equal(room.sourceUrl, "");
  assert.equal(room.opacity, 1);
  assert.equal(room.transitionMs, 0);
  assert.equal(room.model.cameraFov, 100);
  assert.equal(room.model.backgroundColor, "#10131a");
});

test("Live2D 場景保留獨立縮放、位置與視差設定", () => {
  const normalized = normalizeSceneStore({
    version: 1,
    activeSceneId: "animated-lab",
    customScenes: [
      {
        ...createScenePreset("animated-lab", "live2d", "Animated lab"),
        sourceUrl: "/live2d-models/lab/lab.model3.json",
        live2d: {
          scale: 99,
          x: -9,
          y: 2,
          parallax: 2,
        },
      },
    ],
  });
  const scene = normalized.customScenes[0];
  assert.equal(scene.type, "live2d");
  assert.deepEqual(scene.live2d, {
    scale: 10,
    x: -5,
    y: 2,
    parallax: 1,
  });
});

test("重複 ID、冒用內建 ID 與失效的演出綁定會被移除", () => {
  const scene = createScenePreset("room", "image", "Room");
  const normalized = normalizeSceneStore({
    version: 1,
    activeSceneId: "missing",
    customScenes: [
      scene,
      { ...scene, name: "Duplicate" },
      { ...scene, id: CURRENT_BACKGROUND_SCENE_ID },
    ],
    performanceBindings: {
      valid: { sceneId: "room", restoreAfter: true },
      missing: { sceneId: "missing", restoreAfter: false },
    },
  });
  assert.deepEqual(
    normalized.customScenes.map((item) => item.id),
    ["room"],
  );
  assert.equal(normalized.activeSceneId, CURRENT_BACKGROUND_SCENE_ID);
  assert.deepEqual(normalized.performanceBindings, {
    valid: { sceneId: "room", restoreAfter: true },
  });
});

test("讀取場景清單時回傳副本，避免編輯畫面污染儲存資料", () => {
  const store = normalizeSceneStore({
    ...createEmptySceneStore(),
    customScenes: [createScenePreset("room")],
  });
  const presets = getScenePresets(store);
  presets[1].model.cameraPosition[0] = 99;
  assert.equal(store.customScenes[0].model.cameraPosition[0], 0);
});
