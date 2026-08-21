// GPT-SoVITS 語言代碼 → i18n 鍵。
//
// 值域本身的 single source of truth 在後端（perf_route.py 的 GPT_SOVITS_LANGS，
// 經 /api/perf 的 gpt_sovits_langs 送出），這裡只負責「代碼要顯示成什麼字」。
//
// 抽成獨立模組是因為現在有兩個地方要用：語音合成分頁的全域 text_lang／
// prompt_lang，以及角色編輯表單裡的角色發聲語言。各自複製一份 switch 的話，
// 後端新增一個代碼時只會有一邊補上翻譯，另一邊安靜地顯示原始代碼。
//
// 有專屬 i18n 鍵而不是原樣顯示代碼，跟 ttsModelLabelKey 同一個理由。
// zh/en/ja/ko/yue 是 sherpa_onnx_asr 內建 sense_voice 模型本來就覆蓋的語言
// 家族，auto 是 GPT-SoVITS 自己的語言自動偵測。找不到對應鍵時（後端清單日後
// 加了新代碼）直接顯示原始代碼。
export function gptSovitsLangLabelKey(code: string): string | null {
  switch (code) {
    case 'zh': return 'settings.perf.gptSovitsLangZh';
    case 'en': return 'settings.perf.gptSovitsLangEn';
    case 'ja': return 'settings.perf.gptSovitsLangJa';
    case 'ko': return 'settings.perf.gptSovitsLangKo';
    case 'yue': return 'settings.perf.gptSovitsLangYue';
    case 'auto': return 'settings.perf.gptSovitsLangAuto';
    default: return null;
  }
}
