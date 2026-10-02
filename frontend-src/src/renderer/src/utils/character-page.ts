// 角色頁的純判斷。抽出來是為了能測：左右版面、六區、哪些動作只對正在用的
// 角色有意義，這些規則寫在元件裡就只能靠手點。

export type SkinType = 'live2d' | 'vrm'

export interface SkinOption {
  name: string
  type: SkinType
}

// 「正在用」看 conf_uid，不看名字：兩個角色可以取同一個名字。
export const isActiveCharacter = (
  record: { conf_uid: string | null },
  activeConfUid: string,
): boolean => Boolean(activeConfUid) && record.conf_uid === activeConfUid

export const skinTypeOf = (skins: SkinOption[], modelName: string): SkinType | null =>
  skins.find((skin) => skin.name === modelName)?.type ?? null

// 只有畫面上那個模型能試播，存檔後也只有它的點擊動作要即時換掉。
export const isLoadedModel = (editing: string | undefined, loaded: string | undefined): boolean =>
  Boolean(editing) && editing === loaded

const INHERIT = '__inherit__'

// 聲音區：選了哪個引擎就只出現它的欄位。沿用全域時不知道全域是哪個，兩組都給；
// 其他引擎的參數不在角色檔裡，兩組都不給。
export const voiceFieldGroups = (engine: string): { edge: boolean; gptSovits: boolean } => {
  if (engine === '' || engine === INHERIT) return { edge: true, gptSovits: true }
  return { edge: engine === 'edge_tts', gptSovits: engine === 'gpt_sovits_tts' }
}

// 清單重抓之後右邊要顯示誰：原本選的還在就留著；不在了（被刪掉）就回到正在用的
// 那個；連那個都找不到就第一筆。waitingFor 是剛建立、清單還沒重抓到的那一個：
// 等她出現就選她，出現之前不動（不然會先跳去正在用的那個，新角色就選不到了）。
export const nextSelection = (
  records: { filename: string; conf_uid: string | null }[],
  selected: string | null,
  activeConfUid: string,
  waitingFor: string | null = null,
): string | null => {
  if (waitingFor) return records.some((r) => r.filename === waitingFor) ? waitingFor : selected
  if (selected && records.some((r) => r.filename === selected)) return selected
  const active = records.find((r) => isActiveCharacter(r, activeConfUid))
  return (active ?? records[0])?.filename ?? null
}

// 正在用的角色：經 WebSocket 立刻換，她馬上用新的說法。其他角色：存起來，
// 切換到她時才生效。
export const personaApplyMode = (isActive: boolean): 'live' | 'stored' => (isActive ? 'live' : 'stored')
