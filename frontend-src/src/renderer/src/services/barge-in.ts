// 她講話時你開口：要不要打斷她。
//
// 以前一聽到人聲（VAD 確認後約 0.1–0.3 秒）就立刻打斷，你邊聽邊「嗯」「對」，
// 她一句話都講不完。現在：
// - 出聲不到 BARGE_IN_AFTER_MS 就停的，是附和——不打斷、也不送出去。
// - 講超過這個長度才算插話：叫後端停下、清掉還沒播的句子，但正在播的那一句
//   讓她講完（use-interrupt 的 finishSentence），不在句子中間斷掉。

export const BARGE_IN_AFTER_MS = 1000

export function speechEndAction(
  { duringHerTurn, bargedIn }: { duringHerTurn: boolean, bargedIn: boolean },
): 'send' | 'drop' {
  return duringHerTurn && !bargedIn ? 'drop' : 'send'
}
