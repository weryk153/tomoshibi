import { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from 'react';
import {
  loadThemePreference, normalizeThemePreference, resolveTheme, saveThemePreference,
  THEME_STORAGE_KEY, type ThemePreference,
} from '@/theme/theme-preference';

const SYSTEM_THEME_QUERY = '(prefers-color-scheme: dark)';

function readPreference(): ThemePreference {
  // Accessing localStorage itself can throw in restricted browser contexts.
  try { return loadThemePreference(window.localStorage); } catch { return 'light'; }
}

/** Called before React and the avatar SDK load, avoiding a light flash on startup. */
export function initializeAppTheme(): void {
  document.documentElement.dataset.appTheme = resolveTheme(
    readPreference(), window.matchMedia(SYSTEM_THEME_QUERY).matches,
  );
}

interface ThemeContextValue {
  preference: ThemePreference;
  setPreference: (preference: ThemePreference) => void;
}
const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }): JSX.Element {
  const [preference, setPreferenceState] = useState(readPreference);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia(SYSTEM_THEME_QUERY).matches);

  useEffect(() => {
    const media = window.matchMedia(SYSTEM_THEME_QUERY);
    const onSystemChange = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    const onStorage = (event: StorageEvent) => {
      if (event.key === THEME_STORAGE_KEY || event.key === null) {
        setPreferenceState(normalizeThemePreference(event.newValue));
      }
    };
    setSystemDark(media.matches);
    media.addEventListener('change', onSystemChange);
    window.addEventListener('storage', onStorage);
    return () => {
      media.removeEventListener('change', onSystemChange);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  useLayoutEffect(() => {
    document.documentElement.dataset.appTheme = resolveTheme(preference, systemDark);
  }, [preference, systemDark]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    try { saveThemePreference(window.localStorage, next); } catch { /* Keep the in-memory choice. */ }
  }, []);
  const value = useMemo(() => ({ preference, setPreference }), [preference, setPreference]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within ThemeProvider');
  return context;
}
