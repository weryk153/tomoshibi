"""機器的硬體資訊。目前只有記憶體總量。

唯一用途是決定首次啟動精靈建議下載哪顆模型。抓不到就回 None，呼叫端用
fallback——這條路徑不得因為硬體資訊抓不到而壞掉。

用 psutil 而不是 stdlib：Windows 沒有 os.sysconf，要 ctypes 手刻
GlobalMemoryStatusEx 的 struct，而這個專案的開發機不是 Windows。在無法驗證的
前提下寫 ctypes 不負責任。
"""

import psutil
from loguru import logger


def total_ram_bytes() -> int | None:
    """實體記憶體總量（位元組）。抓不到回 None。"""
    try:
        total = int(psutil.virtual_memory().total)
    except Exception as e:
        logger.debug(f"[system_probe] 讀不到記憶體總量：{type(e).__name__}")
        return None
    return total if total > 0 else None
