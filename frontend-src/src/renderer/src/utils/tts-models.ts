// TTS 引擎名稱 → i18n 鍵。
//
// 下拉選單的文案有專屬 i18n 鍵，不是後端傳什麼字串就原樣顯示——跟
// utils/gpt-sovits-langs.ts 的 gptSovitsLangLabelKey 同一個理由。
//
// 這個對照原本寫死在 tts.tsx 裡，角色編輯器（characters.tsx）要選引擎時就會
// 需要第二份。兩份各自維護遲早會漂移（合成分頁顯示「GPT-SoVITS」、角色面板
// 顯示原始字串），所以抽到這裡共用。
//
// 找不到對應鍵時回 null，呼叫端顯示原始字串——後端的 tts_models 清單來自
// conf.yaml，使用者可能加了我們沒有翻譯的引擎。
export function ttsModelLabelKey(name: string): string | null {
  if (name === 'edge_tts') return 'settings.perf.ttsEdge';
  if (name === 'gpt_sovits_tts') return 'settings.perf.ttsGptSovits';
  return null;
}
