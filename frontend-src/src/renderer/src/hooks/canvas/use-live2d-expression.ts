import { useCallback } from 'react';

/**
 * Set expression for Live2D model
 * @param expressionValue - Expression name (string) or index (number)
 * @param lappAdapter - LAppAdapter instance
 * @param logMessage - Optional message to log on success
 */
export function setLive2DExpression(
  expressionValue: string | number,
  lappAdapter: any,
  logMessage?: string,
): void {
  try {
    if (typeof expressionValue === 'string') {
      // Set expression by name
      lappAdapter.setExpression(expressionValue);
    } else if (typeof expressionValue === 'number') {
      // Set expression by index
      const expressionName = lappAdapter.getExpressionName(expressionValue);
      if (expressionName) {
        lappAdapter.setExpression(expressionName);
      }
    }
    if (logMessage) {
      console.log(logMessage);
    }
  } catch (error) {
    console.error('Failed to set expression:', error);
  }
}

/**
 * 表情を解除して素の顔に戻す。
 *
 * 「中立の表情を一つ選んで被せる」のではなく、再生中の表情モーションを
 * 止めるだけ。Cubism の表情はパラメータへの加算なので、止めれば素に戻る
 * ——どれが中立かを決める必要がそもそもない。
 *
 * 以前は表情リストの 0 番目を被せていた。0 番目はモデル作者が最初に
 * 並べただけの表情で中立とは限らず、フリーレンの 0 番は「泣き」だった
 * ため、発話が終わって IDLE に戻るたび（live2d.tsx）に泣き顔になっていた。
 *
 * @param lappAdapter - LAppAdapter instance
 */
export function clearLive2DExpression(lappAdapter: any): void {
  if (!lappAdapter) return;

  try {
    const model = lappAdapter.getModel();
    if (!model || !model._modelSetting) {
      console.log('Model or model settings not loaded yet, skipping expression reset');
      return;
    }
    model.clearExpression();
  } catch (error) {
    console.log('Failed to reset expression:', error);
  }
}

/**
 * Custom hook for handling Live2D model expressions
 */
export const useLive2DExpression = () => {
  const setExpression = useCallback(setLive2DExpression, []);
  const resetExpression = useCallback(clearLive2DExpression, []);

  return {
    setExpression,
    resetExpression,
  };
};
