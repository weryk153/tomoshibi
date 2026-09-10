# 舞台特效演出

舞台特效是 Live2D 動作的附加層。角色動作仍由 Cubism 播放；本系統只負責
Cut-in、粒子、掃描線、暗場、閃光、鏡頭效果與簡短合成音效。

## 演出規模

- `accent`：小型點綴，不遮背景、不震動鏡頭。
- `scene`：登場或重要反應，可使用局部暗場、身分卡與鏡頭推近。
- `cinematic`：完整必殺技等級演出，才使用全畫面效果與強烈鏡頭運動。

## Electron 混合渲染

舞台演出使用兩個獨立的 GPU context，不修改或共用 Cubism 的 WebGL
狀態：

- Live2D Canvas：人物網格、表情與 `.motion3.json` 動作。
- 透明 WebGL2 Canvas：程序化能量、掃描光、粒子與衝擊波。
- React/CSS：字幕、Cut-in、HUD、轉場與無 WebGL2 時的完整降級畫面。

WebGL2 層只在演出期間建立，結束後會釋放 shader、buffer、RAF 與
context。渲染解析度的 DPR 上限為 `2`，framebuffer 單邊不超過
`4096px`、總像素不超過約 420 萬，避免 Electron 在 Retina/4K
螢幕上產生不必要的 GPU 負擔。
使用者啟用「減少動態效果」時不建立 WebGL 動畫，保留較溫和的 CSS
演出。

## 觸發方式

開發者工具可直接試播：

```js
window.TomoshibiEffects.play('characterEntrance')
window.TomoshibiEffects.play('characterEntrance', {
  scale: 'accent',
  sound: false,
})
window.TomoshibiEffects.play('cinematicBurst', {
  title: 'SPECIAL MOVE',
  subtitle: 'CUSTOM TITLE',
  intensity: 0.8,
})
window.TomoshibiEffects.stop()
```

後端也可以送 WebSocket 訊息：

```json
{
  "type": "stage-effect",
  "effect": "characterEntrance",
  "effect_options": {
    "characterId": "my_character",
    "scale": "scene",
    "intensity": 1
  }
}
```

## 演出方案管理

設定頁的「演出方案」管理的是可重用的整套演出，而不只是單一特效。每套方案
會一起保存：

- 舞台效果、演出規模、強度、標題與副標題。
- 適用人物與使用情境。
- 播放權重、符合後機率、冷卻時間與避免近期重複。
- 對話關鍵字、時段條件。
- 該方案獨立的配樂、音量與淡入／淡出。

內建方案是唯讀範本；按「複製後調整」即可建立自己的版本。自訂方案和每個
人物的播放池設定會存在 Electron renderer 的 localStorage。音檔仍獨立存在
IndexedDB，不會被寫進設定 JSON 或 Git。

播放池按人物與情境分開設定，可在「人物登場、一般對話、主動對話、手動演出」
之間切換。每個播放池可複選任意數量的相容方案，並選擇：

- `fixed`：播放勾選清單中的第一套。
- `shuffle`：洗牌播放，同一輪內不重複。
- `sequence`：依清單順序輪播。
- `weighted`：依每套方案的權重隨機。
- `conditions`：先套用關鍵字、時段、機率與冷卻，再從符合者洗牌。
- `ai`：只在 AI 明確選擇允許的方案時播放。
- `hybrid`：AI 可優先指定；沒有指定時由本機條件與洗牌選擇。

所有模式都會套用人物、情境、關鍵字、時段、機率與冷卻限制；「測試播放池」
會略過這些限制，方便確認視覺與音樂。自動播放預設關閉，建立或升級設定後不會
突然在對話中播放。

### AI 導演的安全邊界

當一般對話或主動對話的播放池使用 `ai`／`hybrid` 時，前端只把目前人物已
勾選且相容的方案 ID、名稱與描述送給後端。後端將這份 allowlist 加入 system
prompt，模型可在回覆最前面輸出一個：

```text
[stage:preset-id]
```

標籤會在字幕、TTS 與對話記憶前移除。後端拒絕格式不合法或不在 allowlist
內的 ID；前端收到後仍會再次檢查當下人物、情境、條件與冷卻，所以模型不能
直接執行任意效果或繞過使用者設定。AI 也可以不選擇任何演出。

## 與人物動作、畫面互動同步

人物 binding 會在時間軸指定位置送出兩種瀏覽器事件：

- `tomoshibi:stage-motion-cue`：交給身體動作系統播放 Cubism motion。
- `tomoshibi:stage-interaction-cue`：交給畫面互動系統執行聚焦、掃描、
  撞擊或釋放效果。

`registerStageEffectBinding()` 可為真正擁有該演出的人物登記標題、配色、
身體動作與互動 cue。未登記的人物使用通用視覺，不會硬播其他人物的動作。

Cubism 有標準參數 ID 與檔案格式，但沒有跨模型通用的完整動作名稱。因此 motion
cue 同時帶有 Tomoshibi 語意動作 `actionId`（例如 `greeting`、`thinking`、
`signature`）與可選的 Cubism `group/index` 回退。3a 應優先依目前人物解析
`actionId`，找不到映射時才播放回退 motion。

## 自訂演出配樂

Live2D 設定頁可替目前人物的登場演出選擇 MP3、WAV、OGG 或 M4A（上限
30MB）；「演出方案」頁也能替每套方案選擇自己的音樂。音檔以
「人物 ID＋方案 ID」存進這臺裝置的 IndexedDB，不會加入 Git、上傳後端或
分享給其他使用者。舊版設定在 `characterEntrance` 音樂槽中的登場音樂，會在
方案沒有專屬音樂時自動作為後備，不必重新選檔。

人物 binding 可設定音量、起播時間與淡入／淡出。沒有自訂音檔、瀏覽器拒絕
自動播放，或檔案已被移除時，演出會退回內建的短合成提示音。停止或切換演出會
讓目前配樂同步淡出。
