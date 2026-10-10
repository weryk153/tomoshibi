export const THEME_STORAGE_KEY = 'tomoshibi-ui-theme';
export const THEME_OPTIONS = ['light', 'dark', 'sakura', 'mint', 'abyss', 'caramel', 'system'] as const;
export type ThemePreference = (typeof THEME_OPTIONS)[number];
export type ResolvedTheme = Exclude<ThemePreference, 'system'>;

// Keep the existing appearance until someone explicitly chooses another theme.
export function normalizeThemePreference(value: unknown): ThemePreference {
  return THEME_OPTIONS.includes(value as ThemePreference) ? value as ThemePreference : 'light';
}

export function resolveTheme(preference: ThemePreference, systemDark: boolean): ResolvedTheme {
  return preference === 'system' ? (systemDark ? 'dark' : 'light') : preference;
}

export function loadThemePreference(storage: Pick<Storage, 'getItem'>): ThemePreference {
  try {
    return normalizeThemePreference(storage.getItem(THEME_STORAGE_KEY));
  } catch {
    return 'light';
  }
}

export function saveThemePreference(storage: Pick<Storage, 'setItem'>, preference: ThemePreference): void {
  try {
    storage.setItem(THEME_STORAGE_KEY, preference);
  } catch {
    // Restricted storage must not prevent switching the current page's theme.
  }
}
