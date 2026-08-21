import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  cloneScenePreset,
  createScenePreset,
  createEmptySceneStore,
  getScenePresets,
  normalizeSceneStore,
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

function loadStore(): SceneStore {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved
      ? normalizeSceneStore(JSON.parse(saved))
      : createEmptySceneStore();
  } catch (error) {
    console.warn("[Scene] Could not read saved scene configuration:", error);
    return createEmptySceneStore();
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
  const [store, setStore] = useState<SceneStore>(loadStore);
  const [temporarySceneId, setTemporarySceneId] = useState<string | null>(null);
  const [resolvedSourceUrl, setResolvedSourceUrl] = useState("");
  const temporaryTimerRef = useRef<number | null>(null);
  const scenes = useMemo(() => getScenePresets(store), [store]);
  const activeSceneId = temporarySceneId || store.activeSceneId;
  const activeScene =
    scenes.find((scene) => scene.id === activeSceneId) || scenes[0];

  useEffect(() => saveStore(store), [store]);

  useEffect(() => {
    let alive = true;
    let objectUrl: string | null = null;
    if (!activeScene.assetKey) {
      setResolvedSourceUrl(activeScene.sourceUrl);
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
  }, [activeScene.assetKey, activeScene.assetVersion, activeScene.sourceUrl]);

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
        normalizeSceneStore({
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
      normalizeSceneStore({
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
        normalizeSceneStore({
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
        return normalizeSceneStore({
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
      if (!scene || scene.builtin) return "unsupported";
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
        return normalizeSceneStore({ ...current, performanceBindings });
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
          normalizeSceneStore({
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
