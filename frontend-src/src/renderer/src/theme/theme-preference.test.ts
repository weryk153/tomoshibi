import test from 'node:test';
import assert from 'node:assert/strict';
import {
  THEME_OPTIONS, THEME_STORAGE_KEY, loadThemePreference, normalizeThemePreference, resolveTheme, saveThemePreference,
} from './theme-preference.ts';

test('existing users and invalid saved values retain the light theme', () => {
  for (const value of [null, undefined, '', 'invalid', '"dark"', {}, 0]) {
    assert.equal(normalizeThemePreference(value), 'light');
  }
  assert.equal(loadThemePreference({ getItem: () => null }), 'light');
});

test('system mode follows the OS while explicit choices remain stable', () => {
  assert.equal(resolveTheme('system', false), 'light');
  assert.equal(resolveTheme('system', true), 'dark');
  assert.equal(resolveTheme('dark', false), 'dark');
  assert.equal(resolveTheme('light', true), 'light');
});

test('the preference survives reload without storing the resolved OS appearance', () => {
  const values = new Map<string, string>();
  const storage = { getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => { values.set(key, value); } };
  for (const preference of THEME_OPTIONS) {
    saveThemePreference(storage, preference);
    assert.equal(loadThemePreference(storage), preference);
    assert.equal(values.get(THEME_STORAGE_KEY), preference);
  }
});

test('restricted storage does not prevent the UI from loading or switching', () => {
  const denied = () => { throw new Error('storage denied'); };
  assert.equal(loadThemePreference({ getItem: denied }), 'light');
  assert.doesNotThrow(() => saveThemePreference({ setItem: denied }, 'dark'));
});

test('named themes retain their identity regardless of the system appearance', () => {
  for (const preference of ['sakura', 'mint', 'abyss', 'caramel'] as const) {
    assert.equal(normalizeThemePreference(preference), preference);
    assert.equal(resolveTheme(preference, false), preference);
    assert.equal(resolveTheme(preference, true), preference);
  }
});
