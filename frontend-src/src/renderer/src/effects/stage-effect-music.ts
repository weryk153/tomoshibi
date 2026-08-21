const DB_NAME = 'tomoshibi-stage-effects';
const DB_VERSION = 1;
const STORE_NAME = 'music';

export const STAGE_EFFECT_MUSIC_MAX_BYTES = 30 * 1024 * 1024;
export const STAGE_EFFECT_MUSIC_TYPES = [
  'audio/mpeg',
  'audio/wav',
  'audio/ogg',
  'audio/mp4',
] as const;
const STAGE_EFFECT_MUSIC_EXTENSIONS = ['.mp3', '.wav', '.ogg', '.m4a'] as const;

export type StageEffectMusicError = 'notAudio' | 'tooLarge' | 'empty';

export interface StageEffectMusicFileLike {
  name: string;
  size: number;
  type: string;
}

export interface StoredStageEffectMusic {
  key: string;
  fileName: string;
  type: string;
  blob: Blob;
  updatedAt: number;
}

export interface StageEffectMusicPlaybackOptions {
  volume: number;
  fadeInMs: number;
  fallbackSlotId?: string;
}

export function stageEffectMusicKey(
  characterId: string,
  slotId: string,
): string {
  return `${characterId.trim()}::${slotId.trim()}`;
}

export function validateStageEffectMusic(
  file: StageEffectMusicFileLike,
): StageEffectMusicError | null {
  if (file.size <= 0) return 'empty';

  const lowerName = file.name.toLowerCase();
  const typeAllowed = (STAGE_EFFECT_MUSIC_TYPES as readonly string[])
    .includes(file.type);
  const extensionAllowed = STAGE_EFFECT_MUSIC_EXTENSIONS
    .some((extension) => lowerName.endsWith(extension));
  if (!typeAllowed && !extensionAllowed) return 'notAudio';
  if (file.size > STAGE_EFFECT_MUSIC_MAX_BYTES) return 'tooLarge';
  return null;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = window.indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'key' });
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

export async function saveStageEffectMusic(
  characterId: string,
  slotId: string,
  file: File,
): Promise<StageEffectMusicError | null> {
  const invalid = validateStageEffectMusic(file);
  if (invalid) return invalid;

  const record: StoredStageEffectMusic = {
    key: stageEffectMusicKey(characterId, slotId),
    fileName: file.name,
    type: file.type,
    blob: file,
    updatedAt: Date.now(),
  };
  await runRequest('readwrite', (store) => store.put(record));
  return null;
}

export async function getStageEffectMusic(
  characterId: string,
  slotId: string,
): Promise<StoredStageEffectMusic | undefined> {
  return runRequest('readonly', (store) => (
    store.get(stageEffectMusicKey(characterId, slotId))
  ));
}

export async function removeStageEffectMusic(
  characterId: string,
  slotId: string,
): Promise<void> {
  await runRequest('readwrite', (store) => (
    store.delete(stageEffectMusicKey(characterId, slotId))
  ));
}

class StageEffectMusicPlayer {
  private audio: HTMLAudioElement | null = null;

  private objectUrl: string | null = null;

  private fadeTimer: number | null = null;

  private requestSequence = 0;

  private cleanup(): void {
    if (this.fadeTimer !== null) {
      window.clearInterval(this.fadeTimer);
      this.fadeTimer = null;
    }
    this.audio?.pause();
    this.audio = null;
    if (this.objectUrl) {
      URL.revokeObjectURL(this.objectUrl);
      this.objectUrl = null;
    }
  }

  async play(
    characterId: string,
    slotId: string,
    options: StageEffectMusicPlaybackOptions,
  ): Promise<boolean> {
    this.requestSequence += 1;
    const request = this.requestSequence;
    this.cleanup();
    let record = await getStageEffectMusic(characterId, slotId);
    if (!record && options.fallbackSlotId && options.fallbackSlotId !== slotId) {
      record = await getStageEffectMusic(characterId, options.fallbackSlotId);
    }
    if (!record || request !== this.requestSequence) return false;

    const objectUrl = URL.createObjectURL(record.blob);
    const audio = new Audio(objectUrl);
    const targetVolume = Math.min(1, Math.max(0, options.volume));
    audio.volume = options.fadeInMs > 0 ? 0 : targetVolume;
    this.objectUrl = objectUrl;
    this.audio = audio;

    try {
      await audio.play();
    } catch (error) {
      console.warn('[StageEffect] Custom music playback was blocked:', error);
      if (this.audio === audio) {
        this.cleanup();
      } else {
        audio.pause();
        URL.revokeObjectURL(objectUrl);
      }
      return false;
    }
    if (request !== this.requestSequence) {
      if (this.audio === audio) {
        this.cleanup();
      } else {
        audio.pause();
        URL.revokeObjectURL(objectUrl);
      }
      return false;
    }

    if (options.fadeInMs > 0) {
      const startedAt = performance.now();
      this.fadeTimer = window.setInterval(() => {
        if (this.audio !== audio) return;
        const progress = Math.min(1, (performance.now() - startedAt) / options.fadeInMs);
        audio.volume = targetVolume * progress;
        if (progress >= 1 && this.fadeTimer !== null) {
          window.clearInterval(this.fadeTimer);
          this.fadeTimer = null;
        }
      }, 32);
    }
    audio.addEventListener('ended', () => {
      if (this.audio === audio) this.cleanup();
    }, { once: true });
    return true;
  }

  stop(fadeOutMs = 300): void {
    this.requestSequence += 1;
    const audio = this.audio;
    if (!audio || fadeOutMs <= 0) {
      this.cleanup();
      return;
    }
    if (this.fadeTimer !== null) {
      window.clearInterval(this.fadeTimer);
    }
    const startedAt = performance.now();
    const initialVolume = audio.volume;
    this.fadeTimer = window.setInterval(() => {
      if (this.audio !== audio) return;
      const progress = Math.min(1, (performance.now() - startedAt) / fadeOutMs);
      audio.volume = initialVolume * (1 - progress);
      if (progress >= 1) this.cleanup();
    }, 32);
  }
}

export const stageEffectMusicPlayer = new StageEffectMusicPlayer();
