import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import i18n from "i18next";
import { useWebSocket } from "./websocket-context";
import {
  cloneScenePreset,
  createScenePreset,
  getScenePresets,
  normalizeSceneStore,
  resolveSceneUrl,
  withoutCameraAtStartup,
  ScenePerformanceBinding,
  ScenePreset,
  SceneStore,
  SceneType,
} from "@/scenes/scene";
import {
  getSceneAsset,
  removeSceneAsset,
  saveSceneAsset,
  SceneAssetError,
} from "@/scenes/scene-asset";

import { withThemeBackground } from "@/scenes/character-background";

const STORAGE_KEY = "tomoshibi-scene-store-v1";

interface SceneContextValue {
  scenes: ScenePreset[];
  activeScene: ScenePreset;
  resolvedSourceUrl: string;
  activateScene: (sceneId: string) => boolean;
  createScene: (type?: SceneType) => string;
  updateScene: (sceneId: string, update: Partial<ScenePreset>) => void;
  deleteScene: (sceneId: string) => void;
  importSceneAsset: (
    sceneId: string,
    file: File,
  ) => Promise<SceneAssetError | null>;
  getPerformanceBinding: (
    performanceId: string,
  ) => ScenePerformanceBinding | null;
  setPerformanceBinding: (
    performanceId: string,
    binding: ScenePerformanceBinding | null,
  ) => void;
  playPerformanceScene: (performanceId: string, durationMs: number) => boolean;
}

const SceneContext = createContext<SceneContextValue | null>(null);

// 存檔前的正規化：場景刪光時補回的預設背景要用介面語言的名字。
function normalizeStore(value: unknown): SceneStore {
  return normalizeSceneStore(value, {
    defaultName: i18n.t("settings.scenes.defaultBackground"),
  });
}

// STORAGE_KEY 名字帶 v1 但不改：改了等於丟掉所有人的場景。裡面存的版本號才是
// 第幾版（見 scenes/scene.ts 的 normalizeSceneStore）。
function loadStore(baseUrl: string): SceneStore {
  const defaultName = i18n.t("settings.scenes.defaultBackground");
  let legacyBackgroundUrl: string | null = null;
  try {
    // 一般頁以前把背景存在這裡（useLocalStorage 存的是 JSON 字串）。第一次載入
    // 第 2 版時轉成「背景」場景。
    const legacy = window.localStorage.getItem("backgroundUrl");
    const parsed: unknown = legacy ? JSON.parse(legacy) : null;
    legacyBackgroundUrl = typeof parsed === "string" ? parsed : null;
  } catch {
    legacyBackgroundUrl = null;
  }
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return normalizeSceneStore(saved ? JSON.parse(saved) : null, {
      legacyBackgroundUrl,
      defaultName,
      baseUrl,
    });
  } catch (error) {
    console.warn("[Scene] Could not read saved scene configuration:", error);
    return normalizeSceneStore(null, { legacyBackgroundUrl, defaultName, baseUrl });
  }
}

function saveStore(store: SceneStore): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch (error) {
    console.warn("[Scene] Could not save scene configuration:", error);
  }
}

function createId(): string {
  const suffix =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().replace(/-/g, "").slice(0, 10)
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`.slice(
          0,
          10,
        );
  return `scene-${suffix}`;
}

export function SceneProvider({
  children,
}: {
  children: React.ReactNode;
}): JSX.Element {
  const { baseUrl } = useWebSocket();
  const [store, setStore] = useState<SceneStore>(
    () => withoutCameraAtStartup(loadStore(baseUrl)),
  );
  const [temporarySceneId, setTemporarySceneId] = useState<string | null>(null);
  const [resolvedSourceUrl, setResolvedSourceUrl] = useState("");
  const temporaryTimerRef = useRef<number | null>(null);
  const scenes = useMemo(
    () => getScenePresets(store).map(withThemeBackground),
    [store],
  );
  const activeSceneId = temporarySceneId || store.activeSceneId;
  const activeScene =
    scenes.find((scene) => scene.id === activeSceneId) || scenes[0];

  useEffect(() => saveStore(store), [store]);

  // 同一個瀏覽器開著別的分頁（例如舞台頁）改了場景：跟著換，不然這邊下一次存檔
  // 會用舊的那份把別的分頁剛改的蓋掉。storage 事件只在別的分頁改了才會來，而且值
  // 沒變不會觸發，所以不會兩邊互相丟來丟去。
  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== STORAGE_KEY || !event.newValue) return;
      try {
        setStore(normalizeStore(JSON.parse(event.newValue)));
      } catch {
        // 壞掉的值不理，下次存檔會蓋回正常的。
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  useEffect(() => {
    let alive = true;
    let objectUrl: string | null = null;
    if (!activeScene.assetKey) {
      setResolvedSourceUrl(resolveSceneUrl(activeScene.sourceUrl, baseUrl));
      return () => undefined;
    }
    setResolvedSourceUrl("");
    getSceneAsset(activeScene.assetKey)
      .then((asset) => {
        if (!alive || !asset) return;
        objectUrl = URL.createObjectURL(asset.blob);
        setResolvedSourceUrl(objectUrl);
      })
      .catch((error) => {
        console.warn("[Scene] Could not load local scene asset:", error);
      });
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [activeScene.assetKey, activeScene.assetVersion, activeScene.sourceUrl, baseUrl]);

  useEffect(
    () => () => {
      if (temporaryTimerRef.current !== null) {
        window.clearTimeout(temporaryTimerRef.current);
      }
    },
    [],
  );

  const activateScene = useCallback(
    (sceneId: string): boolean => {
      const exists = scenes.some((scene) => scene.id === sceneId);
      if (!exists) return false;
      if (temporaryTimerRef.current !== null) {
        window.clearTimeout(temporaryTimerRef.current);
        temporaryTimerRef.current = null;
      }
      setTemporarySceneId(null);
      setStore((current) =>
        normalizeStore({
          ...current,
          activeSceneId: sceneId,
        }),
      );
      return true;
    },
    [scenes],
  );

  const createScene = useCallback((type: SceneType = "image"): string => {
    const id = createId();
    setStore((current) =>
      normalizeStore({
        ...current,
        customScenes: [...current.customScenes, createScenePreset(id, type)],
      }),
    );
    return id;
  }, []);

  const updateScene = useCallback(
    (sceneId: string, update: Partial<ScenePreset>) => {
      const previousAssetKey = scenes.find(
        (scene) => scene.id === sceneId,
      )?.assetKey;
      if (
        Object.prototype.hasOwnProperty.call(update, "assetKey") &&
        previousAssetKey &&
        update.assetKey !== previousAssetKey
      ) {
        removeSceneAsset(previousAssetKey).catch((error) => {
          console.warn("[Scene] Could not remove replaced scene asset:", error);
        });
      }
      setStore((current) =>
        normalizeStore({
          ...current,
          customScenes: current.customScenes.map((scene) =>
            scene.id === sceneId
              ? {
                  ...cloneScenePreset(scene),
                  ...update,
                  id: scene.id,
                  builtin: false,
                  model: update.model
                    ? { ...scene.model, ...update.model }
                    : scene.model,
                  live2d: update.live2d
                    ? { ...scene.live2d, ...update.live2d }
                    : scene.live2d,
                }
              : scene,
          ),
        }),
      );
    },
    [scenes],
  );

  const deleteScene = useCallback(
    (sceneId: string) => {
      const assetKey = scenes.find((scene) => scene.id === sceneId)?.assetKey;
      setStore((current) => {
        const performanceBindings = Object.fromEntries(
          Object.entries(current.performanceBindings).filter(
            ([, binding]) => binding.sceneId !== sceneId,
          ),
        );
        return normalizeStore({
          ...current,
          activeSceneId:
            current.activeSceneId === sceneId
              ? undefined
              : current.activeSceneId,
          customScenes: current.customScenes.filter(
            (scene) => scene.id !== sceneId,
          ),
          performanceBindings,
        });
      });
      if (temporarySceneId === sceneId) setTemporarySceneId(null);
      if (assetKey) {
        removeSceneAsset(assetKey).catch((error) => {
          console.warn("[Scene] Could not remove local scene asset:", error);
        });
      }
    },
    [scenes, temporarySceneId],
  );

  const importSceneAsset = useCallback(
    async (sceneId: string, file: File): Promise<SceneAssetError | null> => {
      const scene = scenes.find((candidate) => candidate.id === sceneId);
      if (!scene) return "unsupported";
      const assetKey = `scene::${sceneId}`;
      const invalid = await saveSceneAsset(assetKey, file, scene.type);
      if (invalid) return invalid;
      updateScene(sceneId, {
        assetKey,
        assetFileName: file.name,
        assetVersion: Date.now(),
        sourceUrl: "",
      });
      return null;
    },
    [scenes, updateScene],
  );

  const getPerformanceBinding = useCallback(
    (performanceId: string) => store.performanceBindings[performanceId] || null,
    [store.performanceBindings],
  );

  const setPerformanceBinding = useCallback(
    (performanceId: string, binding: ScenePerformanceBinding | null) => {
      setStore((current) => {
        const performanceBindings = { ...current.performanceBindings };
        if (binding) performanceBindings[performanceId] = binding;
        else delete performanceBindings[performanceId];
        return normalizeStore({ ...current, performanceBindings });
      });
    },
    [],
  );

  const playPerformanceScene = useCallback(
    (performanceId: string, durationMs: number): boolean => {
      const binding = store.performanceBindings[performanceId];
      if (!binding || !scenes.some((scene) => scene.id === binding.sceneId))
        return false;
      if (temporaryTimerRef.current !== null) {
        window.clearTimeout(temporaryTimerRef.current);
        temporaryTimerRef.current = null;
      }
      if (!binding.restoreAfter) {
        setTemporarySceneId(null);
        setStore((current) =>
          normalizeStore({
            ...current,
            activeSceneId: binding.sceneId,
          }),
        );
        return true;
      }
      setTemporarySceneId(binding.sceneId);
      temporaryTimerRef.current = window.setTimeout(
        () => {
          setTemporarySceneId(null);
          temporaryTimerRef.current = null;
        },
        Math.max(0, durationMs),
      );
      return true;
    },
    [scenes, store.performanceBindings],
  );

  const value = useMemo<SceneContextValue>(
    () => ({
      scenes,
      activeScene,
      resolvedSourceUrl,
      activateScene,
      createScene,
      updateScene,
      deleteScene,
      importSceneAsset,
      getPerformanceBinding,
      setPerformanceBinding,
      playPerformanceScene,
    }),
    [
      scenes,
      activeScene,
      resolvedSourceUrl,
      activateScene,
      createScene,
      updateScene,
      deleteScene,
      importSceneAsset,
      getPerformanceBinding,
      setPerformanceBinding,
      playPerformanceScene,
    ],
  );

  return (
    <SceneContext.Provider value={value}>{children}</SceneContext.Provider>
  );
}

export function useScene(): SceneContextValue {
  const context = useContext(SceneContext);
  if (!context) throw new Error("useScene must be used within SceneProvider");
  return context;
}
