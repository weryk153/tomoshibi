export const SCENE_TYPES = ["image", "video", "live2d", "model3d"] as const;
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
  version: 1;
  activeSceneId: string;
  customScenes: ScenePreset[];
  performanceBindings: Record<string, ScenePerformanceBinding>;
}

export const CURRENT_BACKGROUND_SCENE_ID = "current-background";

export const CURRENT_BACKGROUND_SCENE: ScenePreset = {
  id: CURRENT_BACKGROUND_SCENE_ID,
  builtin: true,
  name: "Current background",
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

export function createEmptySceneStore(): SceneStore {
  return {
    version: 1,
    activeSceneId: CURRENT_BACKGROUND_SCENE_ID,
    customScenes: [],
    performanceBindings: {},
  };
}

export function createScenePreset(
  id: string,
  type: SceneType = "image",
  name = "New scene",
): ScenePreset {
  return {
    ...cloneScenePreset(CURRENT_BACKGROUND_SCENE),
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

  const defaults = CURRENT_BACKGROUND_SCENE.model;
  const live2dDefaults = CURRENT_BACKGROUND_SCENE.live2d;
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
  return [
    cloneScenePreset(CURRENT_BACKGROUND_SCENE),
    ...store.customScenes.map(cloneScenePreset),
  ];
}

export function normalizeSceneStore(value: unknown): SceneStore {
  if (!value || typeof value !== "object") return createEmptySceneStore();
  const raw = value as Partial<SceneStore>;
  const usedIds = new Set([CURRENT_BACKGROUND_SCENE_ID]);
  const customScenes = Array.isArray(raw.customScenes)
    ? raw.customScenes
        .map(normalizeScene)
        .filter((scene): scene is ScenePreset => {
          if (!scene || usedIds.has(scene.id)) return false;
          usedIds.add(scene.id);
          return true;
        })
        .slice(0, 100)
    : [];
  const activeSceneId = usedIds.has(String(raw.activeSceneId))
    ? String(raw.activeSceneId)
    : CURRENT_BACKGROUND_SCENE_ID;
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
    version: 1,
    activeSceneId,
    customScenes,
    performanceBindings,
  };
}
