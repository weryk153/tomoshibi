import { DEFAULT_BACKGROUND_PATH, DEFAULT_SCENE_ID, type ScenePreset } from './scene.ts';

export const WITCH_BACKGROUND = '/bg/moonlight-witch-room.png';
/** 另一張內建背景：沒有角色、不綁任何角色，在「舞台 › 內建背景」自己選。 */
export const STARLIGHT_BACKGROUND = '/bg/starlight-train-room.png';

/** 月光主題的預設背景。只換沒動過的預設場景：使用者自己選的、上傳的、演出用的
 * 背景都不動。不看是哪個角色——角色是使用者自己的，App 不替特定角色寫死背景。 */
export function withThemeBackground(scene: ScenePreset): ScenePreset {
  if (scene.id !== DEFAULT_SCENE_ID || scene.type !== 'image' || scene.assetKey
      || scene.sourceUrl !== DEFAULT_BACKGROUND_PATH) return scene;
  return { ...scene, sourceUrl: WITCH_BACKGROUND };
}
