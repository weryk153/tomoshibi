/**
 * 麥克風行為的三個模式，與底下四個布林值之間的換算。
 *
 * 這四個值（micOn / autoStopMic / autoStartMicOn / autoStartMicOnConvEnd）是
 * vad-context 存在 localStorage 的原始狀態，理論上有 16 種組合，實際上只有三種
 * 講得出用途：
 *
 *   持續開著        麥克風一直開著，你講完也不關。可以隨時插話打斷她。要戴耳機，
 *                   不然她會聽到自己的聲音、把自己講的話當成你在講話。
 *   偵測到聲音才收  你講完就自動關，她回完再自動打開。全程不用碰麥克風鍵，
 *                   一來一往；她講話的時候麥克風是關的，所以不會回授。
 *   主動按麥克風    平常關著。按一下麥克風講話，講完自動關；下次要講再按。
 *                   環境吵、或不想被隨時收音時用這個。
 *
 * autoStopMic 的語意要看清楚：它是「**你**講完話時關麥克風」，在 vad-context 的
 * handleSpeechEnd 裡呼叫 stopMic()。設定頁原本的標籤寫成「AI 開始說話時自動關閉
 * 麥克風」，是錯的——模式說明照著那個標籤寫，也跟著錯過一輪。
 *
 * 剩下十幾種組合不是錯的，只是沒有名字。使用者手動改開關改出那種狀態時
 * resolveMicMode 回 'custom'，UI 顯示「自訂」而不是硬掛一個已經不成立的模式
 * 名稱——選單寫著 A、實際行為是 B 是這個專案明確要消滅的那種介面。
 */

export type MicMode = 'always' | 'vad' | 'push' | 'custom'
export type NamedMicMode = Exclude<MicMode, 'custom'>

export interface MicState {
  micOn: boolean
  autoStopMic: boolean
  autoStartMicOn: boolean
  autoStartMicOnConvEnd: boolean
}

export function resolveMicMode(state: MicState): MicMode {
  const { micOn, autoStopMic, autoStartMicOn, autoStartMicOnConvEnd } = state

  // 兩個自動開啟都要成立，麥克風才算「會自己回來」——少一個就會出現「講完一輪
  // 之後就再也不聽了」這種說不出名字的狀態。
  if (micOn && autoStartMicOn && autoStartMicOnConvEnd) {
    return autoStopMic ? 'vad' : 'always'
  }

  // 主動按麥克風：沒有任何自動開啟，而且你講完就關。
  //
  // 這裡刻意不看 micOn——這個模式下它一直在變（按下去講話時是開的，講完自動
  // 關），納入判定的話模式會在講話中途跳成「自訂」。
  if (!autoStartMicOn && !autoStartMicOnConvEnd && autoStopMic) {
    return 'push'
  }

  return 'custom'
}

export function micModeState(mode: NamedMicMode): MicState {
  switch (mode) {
    case 'always':
      return {
        micOn: true,
        autoStopMic: false,
        autoStartMicOn: true,
        autoStartMicOnConvEnd: true,
      }
    case 'vad':
      return {
        micOn: true,
        autoStopMic: true,
        autoStartMicOn: true,
        autoStartMicOnConvEnd: true,
      }
    case 'push':
    default:
      return {
        // 切過去就先關起來——這個模式的前提是「平常關著，要講才按」，
        // 切過去卻還開著會繼續收音。
        micOn: false,
        autoStopMic: true,
        autoStartMicOn: false,
        autoStartMicOnConvEnd: false,
      }
  }
}

/**
 * 後端送來的 `start-mic` 控制訊息該不該照做。
 *
 * websocket_handler 在每個 WebSocket 連上時都無條件送一次 start-mic，而前端原本
 * 收到就直接 startMic()。麥克風偏好整個活在瀏覽器的 localStorage 裡，後端不可能
 * 知道，所以那個訊息實際上是「我這邊準備好了」而不是「請打開麥克風」。照單全收
 * 的話，設成「主動按麥克風」也會在每次重整後被打開，然後開始把環境噪音辨識成
 * 句子送給角色（實際看到的：「的話海沒在被設並的進行拘留。」）。
 *
 * 只有「主動按麥克風」是硬否決——那個模式的定義就是不自己開。其他模式（含自訂）
 * 都放行：使用者留著任何一個自動開啟的設定，就代表他確實要它自己開。
 */
export function shouldHonourStartMic(state: MicState): boolean {
  return resolveMicMode(state) !== 'push'
}
