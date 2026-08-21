import {
  createContext, useMemo, useContext, useState, useCallback, useEffect, useRef,
} from 'react';
import { useLocalStorage } from '@/hooks/utils/use-local-storage';
import { useWebSocket } from './websocket-context';

/**
 * Background file interface
 * @interface BackgroundFile
 */
interface BackgroundFile {
  name: string;
  url: string;
}

/**
 * Background URL context state interface
 * @interface BgUrlContextState
 */
export interface BgUrlContextState {
  backgroundUrl: string;
  setBackgroundUrl: (url: string) => void;
  backgroundFiles: BackgroundFile[];
  setBackgroundFiles: (files: BackgroundFile[]) => void;
  resetBackground: () => void;
  addBackgroundFile: (file: BackgroundFile) => void;
  removeBackgroundFile: (name: string) => void;
  isDefaultBackground: boolean;
  useCameraBackground: boolean;
  setUseCameraBackground: (use: boolean) => void;
}

/**
 * Create the background URL context
 */
const BgUrlContext = createContext<BgUrlContextState | null>(null);

/**
 * Background URL Provider Component
 * @param {Object} props - Provider props
 * @param {React.ReactNode} props.children - Child components
 */
export function BgUrlProvider({ children }: { children: React.ReactNode }) {
  const { baseUrl } = useWebSocket();
  const DEFAULT_BACKGROUND = `${baseUrl}/bg/ceiling-window-room-night.jpeg`;

  // Web keeps using localStorage. Electron also mirrors the value to the main
  // process's userData directory so dev (http://localhost) and packaged
  // (file://) builds restore the same background instead of maintaining two
  // origin-scoped localStorage values.
  const [backgroundUrl, setLocalBackgroundUrl] = useLocalStorage<string>(
    'backgroundUrl',
    DEFAULT_BACKGROUND,
  );
  const initialBackgroundUrl = useRef(backgroundUrl);
  const backgroundChangedSinceMount = useRef(false);

  const setBackgroundUrl = useCallback((url: string) => {
    backgroundChangedSinceMount.current = true;
    setLocalBackgroundUrl(url);
    void window.api?.setBackgroundPreferences?.(url).catch((error: unknown) => {
      console.error('Failed to persist Electron background preference:', error);
    });
  }, [setLocalBackgroundUrl]);

  useEffect(() => {
    let cancelled = false;
    const electronApi = window.api;
    if (!electronApi?.getBackgroundPreferences) return undefined;

    void electronApi.getBackgroundPreferences().then((preferences: { backgroundUrl?: string } | null) => {
      if (cancelled || backgroundChangedSinceMount.current) return;
      const savedUrl = preferences?.backgroundUrl?.trim();
      if (savedUrl) {
        setLocalBackgroundUrl(savedUrl);
      } else {
        void electronApi.setBackgroundPreferences?.(initialBackgroundUrl.current).catch((error: unknown) => {
          console.error('Failed to migrate Electron background preference:', error);
        });
      }
    }).catch((error: unknown) => {
      console.error('Failed to restore Electron background preference:', error);
    });

    return () => {
      cancelled = true;
    };
  }, [setLocalBackgroundUrl]);

  // State for background files list
  const [backgroundFiles, setBackgroundFiles] = useState<BackgroundFile[]>([]);

  // Reset background to default
  const resetBackground = useCallback(() => {
    setBackgroundUrl(DEFAULT_BACKGROUND);
  }, [setBackgroundUrl, DEFAULT_BACKGROUND]);

  // Add new background file
  const addBackgroundFile = useCallback((file: BackgroundFile) => {
    setBackgroundFiles((prev) => [...prev, file]);
  }, []);

  // Remove background file
  const removeBackgroundFile = useCallback((name: string) => {
    setBackgroundFiles((prev) => prev.filter((file) => file.name !== name));
  }, []);

  // Check if current background is default
  const isDefaultBackground = useMemo(
    () => backgroundUrl === DEFAULT_BACKGROUND,
    [backgroundUrl, DEFAULT_BACKGROUND],
  );

  const [useCameraBackground, setUseCameraBackground] = useState<boolean>(false);

  // Memoized context value
  const contextValue = useMemo(() => ({
    backgroundUrl,
    setBackgroundUrl,
    backgroundFiles,
    setBackgroundFiles,
    resetBackground,
    addBackgroundFile,
    removeBackgroundFile,
    isDefaultBackground,
    useCameraBackground,
    setUseCameraBackground,
  }), [backgroundUrl, setBackgroundUrl, backgroundFiles, resetBackground, addBackgroundFile, removeBackgroundFile, isDefaultBackground, useCameraBackground]);

  return (
    <BgUrlContext.Provider value={contextValue}>
      {children}
    </BgUrlContext.Provider>
  );
}

/**
 * Custom hook to use the background URL context
 * @throws {Error} If used outside of BgUrlProvider
 */
export function useBgUrl() {
  const context = useContext(BgUrlContext);

  if (!context) {
    throw new Error('useBgUrl must be used within a BgUrlProvider');
  }

  return context;
}
