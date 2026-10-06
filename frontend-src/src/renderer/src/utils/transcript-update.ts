/**
 * 語音輪先顯示 ASR 的原始字，後端修好後送 user-input-transcription-updated。
 * 只在最後一則是使用者訊息、且還是那句原始字時才換——中間若已經有她的回覆
 * 或使用者又打了別的，就不去改一則對不上的訊息。
 */
export function applyTranscriptUpdate<M extends { role: string; content: string }>(
  messages: M[],
  raw: string,
  fixed: string,
): M[] {
  const last = messages[messages.length - 1];
  if (!last || last.role !== 'human' || last.content !== raw) return messages;
  return [...messages.slice(0, -1), { ...last, content: fixed }];
}
