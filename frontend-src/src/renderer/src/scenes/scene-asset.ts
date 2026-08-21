import type { SceneType } from "./scene.ts";

const DB_NAME = "tomoshibi-scene-assets";
const DB_VERSION = 1;
const STORE_NAME = "assets";

const MAX_BYTES: Record<SceneType, number> = {
  image: 24 * 1024 * 1024,
  video: 250 * 1024 * 1024,
  live2d: 0,
  model3d: 120 * 1024 * 1024,
};

const EXTENSIONS: Record<SceneType, readonly string[]> = {
  image: [".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"],
  video: [".mp4", ".webm", ".mov", ".m4v", ".ogv"],
  live2d: [],
  model3d: [".glb"],
};

export type SceneAssetError = "empty" | "unsupported" | "tooLarge";

export interface SceneAssetFileLike {
  name: string;
  size: number;
  type: string;
}

export interface StoredSceneAsset {
  key: string;
  fileName: string;
  type: string;
  sceneType: SceneType;
  blob: Blob;
  updatedAt: number;
}

function extensionMatches(name: string, type: SceneType): boolean {
  const lowerName = name.toLocaleLowerCase();
  return EXTENSIONS[type].some((extension) => lowerName.endsWith(extension));
}

export function inferSceneAssetType(
  file: SceneAssetFileLike,
): SceneType | null {
  if (file.type.startsWith("image/") || extensionMatches(file.name, "image"))
    return "image";
  if (file.type.startsWith("video/") || extensionMatches(file.name, "video"))
    return "video";
  if (
    file.type === "model/gltf-binary" ||
    extensionMatches(file.name, "model3d")
  )
    return "model3d";
  return null;
}

export function validateSceneAsset(
  file: SceneAssetFileLike,
  expectedType?: SceneType,
): SceneAssetError | null {
  if (file.size <= 0) return "empty";
  const type = inferSceneAssetType(file);
  if (!type || (expectedType && expectedType !== type)) return "unsupported";
  if (file.size > MAX_BYTES[type]) return "tooLarge";
  return null;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME, { keyPath: "key" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function runRequest<T>(
  mode: IDBTransactionMode,
  execute: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDatabase();
  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, mode);
      const request = execute(transaction.objectStore(STORE_NAME));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
      transaction.onerror = () => reject(transaction.error);
    });
  } finally {
    database.close();
  }
}

export async function saveSceneAsset(
  key: string,
  file: File,
  expectedType?: SceneType,
): Promise<SceneAssetError | null> {
  const invalid = validateSceneAsset(file, expectedType);
  if (invalid) return invalid;
  const sceneType = inferSceneAssetType(file);
  if (!sceneType) return "unsupported";
  const record: StoredSceneAsset = {
    key,
    fileName: file.name,
    type: file.type,
    sceneType,
    blob: file,
    updatedAt: Date.now(),
  };
  await runRequest("readwrite", (store) => store.put(record));
  return null;
}

export async function getSceneAsset(
  key: string,
): Promise<StoredSceneAsset | undefined> {
  return runRequest("readonly", (store) => store.get(key));
}

export async function removeSceneAsset(key: string): Promise<void> {
  await runRequest("readwrite", (store) => store.delete(key));
}
