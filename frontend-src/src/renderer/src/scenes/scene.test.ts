import assert from "node:assert/strict";
import test from "node:test";
import {
  createEmptySceneStore,
  createScenePreset,
  DEFAULT_BACKGROUND_PATH,
  DEFAULT_SCENE_ID,
  getScenePresets,
  normalizeSceneStore,
  resolveSceneUrl,
} from "./scene.ts";

test("新安裝有一個普通的背景場景，而且正在用它", () => {
  const store = createEmptySceneStore("背景");
  assert.equal(store.version, 2);
  assert.deepEqual(store.customScenes.map((s) => [s.id, s.type, s.sourceUrl, s.builtin]), [
    [DEFAULT_SCENE_ID, "image", DEFAULT_BACKGROUND_PATH, false],
  ]);
  assert.equal(store.activeSceneId, DEFAULT_SCENE_ID);
});

test("migrates a legacy background url: 一般頁換過的背景變成背景場景", () => {
  const store = normalizeSceneStore(null, {
    legacyBackgroundUrl: "http://127.0.0.1:12393/bg/cozy.jpeg",
    defaultName: "背景",
  });
  assert.equal(store.customScenes[0].id, DEFAULT_SCENE_ID);
  assert.equal(store.customScenes[0].sourceUrl, "http://127.0.0.1:12393/bg/cozy.jpeg");
  assert.equal(store.customScenes[0].name, "背景");
  assert.equal(store.activeSceneId, DEFAULT_SCENE_ID);
});

test("第 1 版的儲存：保留自訂場景與正在用的那個，前面補上轉換來的背景場景", () => {
  const room = createScenePreset("room", "video", "Room");
  const store = normalizeSceneStore(
    { version: 1, activeSceneId: "room", customScenes: [room], performanceBindings: {} },
    { legacyBackgroundUrl: null, defaultName: "背景" },
  );
  assert.deepEqual(store.customScenes.map((s) => s.id), [DEFAULT_SCENE_ID, "room"]);
  assert.equal(store.customScenes[0].sourceUrl, DEFAULT_BACKGROUND_PATH);
  assert.equal(store.activeSceneId, "room");
});

test("keeps performance bindings to the old background", () => {
  const store = normalizeSceneStore(
    {
      version: 1,
      activeSceneId: "current-background",
      customScenes: [],
      performanceBindings: { finale: { sceneId: "current-background", restoreAfter: true } },
    },
    { defaultName: "背景" },
  );
  assert.deepEqual(store.performanceBindings, {
    finale: { sceneId: DEFAULT_SCENE_ID, restoreAfter: true },
  });
});

test("第 2 版不再轉換：刪掉的背景場景不會自己長回來", () => {
  const room = createScenePreset("room", "image", "Room");
  const store = normalizeSceneStore(
    { version: 2, activeSceneId: "room", customScenes: [room], performanceBindings: {} },
    { legacyBackgroundUrl: "http://x/bg/old.jpeg", defaultName: "背景" },
  );
  assert.deepEqual(store.customScenes.map((s) => s.id), ["room"]);
});

test("never leaves the store empty: 全部刪光就補一個預設背景", () => {
  const store = normalizeSceneStore(
    { version: 2, activeSceneId: "gone", customScenes: [], performanceBindings: {} },
    { defaultName: "背景" },
  );
  assert.deepEqual(store.customScenes.map((s) => s.id), [DEFAULT_SCENE_ID]);
  assert.equal(store.activeSceneId, DEFAULT_SCENE_ID);
});

test("攝影機是一種場景", () => {
  const store = normalizeSceneStore({
    version: 2,
    activeSceneId: "cam",
    customScenes: [createScenePreset("cam", "camera", "Camera")],
    performanceBindings: {},
  });
  assert.equal(store.customScenes[0].type, "camera");
  assert.equal(store.activeSceneId, "cam");
});

test("伺服器上的相對路徑接上後端位址；完整網址與 blob 原樣", () => {
  assert.equal(resolveSceneUrl("/bg/a.jpeg", "http://127.0.0.1:12393"), "http://127.0.0.1:12393/bg/a.jpeg");
  assert.equal(resolveSceneUrl("/bg/a.jpeg", "http://127.0.0.1:12393/"), "http://127.0.0.1:12393/bg/a.jpeg");
  assert.equal(resolveSceneUrl("https://x.test/a.png", "http://h"), "https://x.test/a.png");
  assert.equal(resolveSceneUrl("blob:abc", "http://h"), "blob:abc");
  assert.equal(resolveSceneUrl("//cdn.test/a.png", "http://h"), "//cdn.test/a.png");
  assert.equal(resolveSceneUrl("", "http://h"), "");
});

test("場景資料正規化限制數值並阻擋可執行 URL", () => {
  const normalized = normalizeSceneStore({
    version: 2,
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
    version: 2,
    activeSceneId: "animated-lab",
    customScenes: [
      {
        ...createScenePreset("animated-lab", "live2d", "Animated lab"),
        sourceUrl: "/live2d-models/lab/lab.model3.json",
        live2d: { scale: 99, x: -9, y: 2, parallax: 2 },
      },
    ],
  });
  assert.deepEqual(normalized.customScenes[0].live2d, { scale: 10, x: -5, y: 2, parallax: 1 });
});

test("重複 ID 與失效的演出綁定會被移除", () => {
  const scene = createScenePreset("room", "image", "Room");
  const normalized = normalizeSceneStore({
    version: 2,
    activeSceneId: "missing",
    customScenes: [scene, { ...scene, name: "Duplicate" }],
    performanceBindings: {
      valid: { sceneId: "room", restoreAfter: true },
      missing: { sceneId: "missing", restoreAfter: false },
    },
  });
  assert.deepEqual(normalized.customScenes.map((item) => item.id), ["room"]);
  assert.equal(normalized.activeSceneId, "room");
  assert.deepEqual(normalized.performanceBindings, { valid: { sceneId: "room", restoreAfter: true } });
});

test("讀取場景清單時回傳副本，避免編輯畫面污染儲存資料", () => {
  const store = createEmptySceneStore("背景");
  const presets = getScenePresets(store);
  presets[0].model.cameraPosition[0] = 99;
  assert.equal(store.customScenes[0].model.cameraPosition[0], 0);
});
