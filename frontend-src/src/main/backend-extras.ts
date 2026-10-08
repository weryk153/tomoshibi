// 選裝套件（例如 faster-whisper）：使用者在設定頁裝過的，後端記在自己資料夾的
// extras.json（optional_extras.py）。每次啟動的 uv sync 只裝鎖定清單裡的東西，
// 不帶上 --extra 的話，裝過的會被清掉。
//
// 不含 Electron，所以能用 node:test 驗證。

// 認得的選裝套件（跟後端 optional_extras.EXTRAS、pyproject 的 optional-dependencies 一致）。
// 不在清單裡的名字不帶，extras.json 被亂改也只能影響這幾個。
export const KNOWN_EXTRAS: readonly string[] = ['faster_whisper'];

export function syncArgs(extras: readonly string[]): string[] {
  const args = ['sync', '--frozen', '--no-dev', '--no-progress'];
  for (const extra of new Set(extras)) {
    if (KNOWN_EXTRAS.includes(extra)) args.push('--extra', extra);
  }
  return args;
}

/** extras.json 的內容；讀不到、壞掉、格式不對都當沒有。 */
export function readExtras(read: () => string): string[] {
  try {
    const value: unknown = JSON.parse(read());
    return Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : [];
  } catch {
    return [];
  }
}
