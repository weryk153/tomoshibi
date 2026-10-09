// 手機直式版的聊天：疊在角色下方，只顯示最近幾則。她正在說的那一則就是字幕
// （appendAIMessage 一句一句接上去，唸到哪句才出現哪句），畫面上會放大標出來。

export interface ChatLineSource {
  id: string
  role: 'ai' | 'human'
  content: string
  name?: string
  type?: string
}

export interface ChatLine extends ChatLineSource {
  /** 她正在說的這一則：放大、加邊條，等於字幕。 */
  live: boolean
}

export function chatLines(
  messages: readonly ChatLineSource[],
  { speaking, limit }: { speaking: boolean, limit: number },
): ChatLine[] {
  const shown = messages
    .filter((m) => m.content && (m.type === undefined || m.type === 'text'))
    .slice(-limit)
  const last = shown[shown.length - 1]
  return shown.map((m) => ({ ...m, live: speaking && m === last && m.role === 'ai' }))
}
