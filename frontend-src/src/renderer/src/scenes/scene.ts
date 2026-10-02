export const SCENE_TYPES = ["image", "video", "live2d", "model3d", "camera"] as const;
export const SCENE_FITS = ["cover", "contain"] as const;

export type SceneType = (typeof SCENE_TYPES)[number];
export type SceneFit = (typeof SCENE_FITS)[number];

export interface SceneModelConfig {
  cameraFov: number;
  cameraPosition: [number, number, number];
  cameraTarget: [number, number, number];
  ambientIntensity: number;
  directionalIntensity: number;
  autoRotate: boolean;
  rotationSpeed: number;
  backgroundColor: string;
}

export interface SceneLive2DConfig {
  scale: number;
  x: number;
  y: number;
  parallax: number;
}

export interface ScenePreset {
  id: string;
  builtin: boolean;
  name: string;
  type: SceneType;
  sourceUrl: string;
  assetKey?: string;
  assetFileName?: string;
  assetVersion?: number;
  fit: SceneFit;
  opacity: number;
  transitionMs: number;
  muted: boolean;
  loop: boolean;
  live2d: SceneLive2DConfig;
  model: SceneModelConfig;
}

export interface ScenePerformanceBinding {
  sceneId: string;
  restoreAfter: boolean;
}

export interface SceneStore {
  // 第 2 版：背景只由場景決定，沒有內建的「目前背景」場景（見 normalizeSceneStore）。
  version: 2;
  activeSceneId: string;
  customScenes: ScenePreset[];
  performanceBindings: Record<string, ScenePerformanceBinding>;
}

// 新場景與正規化時缺欄位的預設值。
const SCENE_DEFAULTS: ScenePreset = {
  id: "",
  builtin: false,
  name: "",
  type: "image",
  sourceUrl: "",
  fit: "cover",
  opacity: 1,
  transitionMs: 500,
  muted: true,
  loop: true,
  live2d: {
    scale: 1,
    x: 0,
    y: 0,
    parallax: 0.12,
  },
  model: {
    cameraFov: 45,
    cameraPosition: [0, 1.6, 5],
    cameraTarget: [0, 1, 0],
    ambientIntensity: 1.2,
    directionalIntensity: 2,
    autoRotate: false,
    rotationSpeed: 0.15,
    backgroundColor: "#10131a",
  },
};

// 預設背景場景沿用舊「目前背景」的 id：舊演出綁的就是這個 id，轉換後直接接上。
export const DEFAULT_SCENE_ID = "current-background";
export const DEFAULT_BACKGROUND_PATH = "/bg/ceiling-window-room-night.jpeg";

export function createDefaultScene(
  name: string,
  sourceUrl = DEFAULT_BACKGROUND_PATH,
): ScenePreset {
  return { ...createScenePreset(DEFAULT_SCENE_ID, "image", name), sourceUrl };
}

// 伺服器上的檔案存成相對路徑（/bg/…），顯示時接上後端位址：桌面版的頁面不是從
// 後端載入的，相對路徑會找錯地方。
export function resolveSceneUrl(sourceUrl: string, baseUrl: string): string {
  if (!sourceUrl.startsWith("/") || sourceUrl.startsWith("//")) return sourceUrl;
  return `${baseUrl.replace(/\/+$/, "")}${sourceUrl}`;
}

// 伺服器 backgrounds/ 底下的一張圖。檔名可能有空白、#、? 之類，要編碼。
export function serverBackgroundUrl(name: string): string {
  return `/bg/${encodeURIComponent(name)}`;
}

const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

// 指向這台後端 /bg/ 的完整網址（以前一般頁存的就是這種）改存相對路徑：換了連線
// 位址（localhost／127.0.0.1／區網）也找得到，內建背景選單也認得。別的網站的網址不動。
function localServerPath(url: string, baseUrl?: string): string {
  try {
    const parsed = new URL(url);
    if (!parsed.pathname.startsWith("/bg/")) return url;
    const sameServer = baseUrl ? parsed.origin === new URL(baseUrl).origin : false;
    return sameServer || LOOPBACK_HOSTS.has(parsed.hostname) ? parsed.pathname : url;
  } catch {
    return url;
  }
}

// 開 app 時不自己打開攝影機：上次停在攝影機場景的話，改用第一個不是攝影機的場景。
// （桌面版的攝影機權限是自動允許的，不改的話每次開 app 鏡頭就亮。）
export function withoutCameraAtStartup(store: SceneStore): SceneStore {
  const active = store.customScenes.find((scene) => scene.id === store.activeSceneId);
  if (active?.type !== "camera") return store;
  const other = store.customScenes.find((scene) => scene.type !== "camera");
  return other ? { ...store, activeSceneId: other.id } : store;
}

export function createEmptySceneStore(defaultName = "Background"): SceneStore {
  return {
    version: 2,
    activeSceneId: DEFAULT_SCENE_ID,
    customScenes: [createDefaultScene(defaultName)],
    performanceBindings: {},
  };
}

export function createScenePreset(
  id: string,
  type: SceneType = "image",
  name = "New scene",
): ScenePreset {
  return {
    ...cloneScenePreset(SCENE_DEFAULTS),
    id,
    builtin: false,
    name,
    type,
    sourceUrl: "",
    assetKey: undefined,
    assetFileName: undefined,
    assetVersion: undefined,
  };
}

export function cloneScenePreset(scene: ScenePreset): ScenePreset {
  return {
    ...scene,
    live2d: { ...scene.live2d },
    model: {
      ...scene.model,
      cameraPosition: [...scene.model.cameraPosition],
      cameraTarget: [...scene.model.cameraTarget],
    },
  };
}

function finiteNumber(
  value: unknown,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  const number = Number(value);
  return Number.isFinite(number)
    ? Math.min(maximum, Math.max(minimum, number))
    : fallback;
}

function normalizeVector(
  value: unknown,
  fallback: [number, number, number],
): [number, number, number] {
  if (!Array.isArray(value) || value.length !== 3) return [...fallback];
  return [
    finiteNumber(value[0], fallback[0], -1000, 1000),
    finiteNumber(value[1], fallback[1], -1000, 1000),
    finiteNumber(value[2], fallback[2], -1000, 1000),
  ];
}

function isSceneType(value: unknown): value is SceneType {
  return typeof value === "string" && SCENE_TYPES.includes(value as SceneType);
}

function isSceneFit(value: unknown): value is SceneFit {
  return typeof value === "string" && SCENE_FITS.includes(value as SceneFit);
}

function normalizeSourceUrl(value: unknown): string {
  const source = String(value || "")
    .trim()
    .slice(0, 2048);
  return /^(javascript|vbscript):/i.test(source) ? "" : source;
}

function normalizeScene(value: unknown): ScenePreset | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Partial<ScenePreset>;
  const id = String(raw.id || "").trim();
  const name = String(raw.name || "").trim() || "Untitled scene";
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/i.test(id)) return null;

  const defaults = SCENE_DEFAULTS.model;
  const live2dDefaults = SCENE_DEFAULTS.live2d;
  const model = raw.model || defaults;
  const live2d = raw.live2d || live2dDefaults;
  const backgroundColor = String(
    model.backgroundColor || defaults.backgroundColor,
  );
  return {
    id,
    builtin: false,
    name: name.slice(0, 80),
    type: isSceneType(raw.type) ? raw.type : "image",
    sourceUrl: normalizeSourceUrl(raw.sourceUrl),
    assetKey:
      String(raw.assetKey || "")
        .trim()
        .slice(0, 96) || undefined,
    assetFileName:
      String(raw.assetFileName || "")
        .trim()
        .slice(0, 180) || undefined,
    assetVersion: raw.assetVersion
      ? finiteNumber(raw.assetVersion, 0, 0, Number.MAX_SAFE_INTEGER)
      : undefined,
    fit: isSceneFit(raw.fit) ? raw.fit : "cover",
    opacity: finiteNumber(raw.opacity, 1, 0.1, 1),
    transitionMs: Math.round(finiteNumber(raw.transitionMs, 500, 0, 5000)),
    muted: raw.muted !== false,
    loop: raw.loop !== false,
    live2d: {
      scale: finiteNumber(live2d.scale, live2dDefaults.scale, 0.05, 10),
      x: finiteNumber(live2d.x, live2dDefaults.x, -5, 5),
      y: finiteNumber(live2d.y, live2dDefaults.y, -5, 5),
      parallax: finiteNumber(live2d.parallax, live2dDefaults.parallax, 0, 1),
    },
    model: {
      cameraFov: finiteNumber(model.cameraFov, defaults.cameraFov, 10, 100),
      cameraPosition: normalizeVector(
        model.cameraPosition,
        defaults.cameraPosition,
      ),
      cameraTarget: normalizeVector(model.cameraTarget, defaults.cameraTarget),
      ambientIntensity: finiteNumber(
        model.ambientIntensity,
        defaults.ambientIntensity,
        0,
        10,
      ),
      directionalIntensity: finiteNumber(
        model.directionalIntensity,
        defaults.directionalIntensity,
        0,
        20,
      ),
      autoRotate: model.autoRotate === true,
      rotationSpeed: finiteNumber(
        model.rotationSpeed,
        defaults.rotationSpeed,
        -3,
        3,
      ),
      backgroundColor: /^#[0-9a-f]{6}$/i.test(backgroundColor)
        ? backgroundColor
        : defaults.backgroundColor,
    },
  };
}

export function getScenePresets(store: SceneStore): ScenePreset[] {
  return store.customScenes.map(cloneScenePreset);
}

export function normalizeSceneStore(
  value: unknown,
  options: { legacyBackgroundUrl?: string | null; defaultName?: string; baseUrl?: string } = {},
): SceneStore {
  const defaultName = options.defaultName ?? "Background";
  const raw = (value && typeof value === "object" ? value : {}) as Partial<
    Omit<SceneStore, "version">
  > & { version?: number };
  // 第 2 版以前（或從沒存過）：舊的「目前背景」是內建場景、背景本身記在一般頁，
  // 這裡一次性轉成一個普通的圖片場景放在最前面。之後刪掉就是刪掉了。
  const legacy = !(typeof raw.version === "number" && raw.version >= 2);
  const usedIds = new Set<string>();
  const scenes: ScenePreset[] = [];
  if (legacy) {
    const legacyUrl = normalizeSourceUrl(options.legacyBackgroundUrl);
    const url = legacyUrl ? localServerPath(legacyUrl, options.baseUrl) : DEFAULT_BACKGROUND_PATH;
    scenes.push(createDefaultScene(defaultName, url));
    usedIds.add(DEFAULT_SCENE_ID);
  }
  if (Array.isArray(raw.customScenes)) {
    raw.customScenes.map(normalizeScene).forEach((scene) => {
      if (!scene || usedIds.has(scene.id) || scenes.length >= 100) return;
      usedIds.add(scene.id);
      scenes.push({ ...scene, sourceUrl: localServerPath(scene.sourceUrl, options.baseUrl) });
    });
  }
  // 全部刪光：補一個預設背景，畫面不會空白。
  if (scenes.length === 0) {
    scenes.push(createDefaultScene(defaultName));
    usedIds.add(DEFAULT_SCENE_ID);
  }
  const activeSceneId = usedIds.has(String(raw.activeSceneId))
    ? String(raw.activeSceneId)
    : scenes[0].id;
  const performanceBindings: Record<string, ScenePerformanceBinding> = {};
  if (raw.performanceBindings && typeof raw.performanceBindings === "object") {
    Object.entries(raw.performanceBindings)
      .slice(0, 200)
      .forEach(([performanceId, item]) => {
        if (!item || typeof item !== "object") return;
        const sceneId = String(
          (item as Partial<ScenePerformanceBinding>).sceneId || "",
        );
        if (!usedIds.has(sceneId)) return;
        performanceBindings[performanceId.slice(0, 96)] = {
          sceneId,
          restoreAfter:
            (item as Partial<ScenePerformanceBinding>).restoreAfter !== false,
        };
      });
  }
  return {
    version: 2,
    activeSceneId,
    customScenes: scenes,
    performanceBindings,
  };
}
