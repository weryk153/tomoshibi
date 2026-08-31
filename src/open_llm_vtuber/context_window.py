"""問推論端：你到底載了多大的 context window。

為什麼要問
----------
專案從不送 num_ctx / max_tokens，payload 只有 model / messages / temperature /
stream / extra_body。window 是使用者在 LM Studio 載入模型時按的滑桿（或 Ollama
的 num_ctx），後端看不到也管不到——超過時是推論端自己靜默砍掉最舊的訊息，畫面上
只會看到她突然變糊、忘記剛講過的話，沒有任何錯誤。

短期記憶的截斷預算因此只能用猜的。同一台機器上的模型 max 從 2,048 到 262,144
都有，任何寫死的常數對某個設定一定是錯的。LM Studio 的 /api/v0/models 會回
loaded_context_length，問一次就不用猜。

為什麼是懶惰探測，不是開機探測
------------------------------
LM Studio 預設 JIT 載入：server 起著，但要等第一個請求進來才把模型讀進記憶體。
開機時去問，答案幾乎一定是「沒有模型載入」——這不是理論，是實測（server 在跑，
五個模型全部 state=not-loaded）。所以探測放在「已經聊到逼近保守預算」那一刻，
那時模型鐵定醒著。

代價是這個函式是同步的、而呼叫端在 event loop 裡。可接受的理由：正面結果永久
快取，負面結果有冷卻時間，而且呼叫端只在超過保守預算後才問——正常對話一次都
不會問到。localhost 的往返是毫秒級，逾時只在推論端卡住時才會踩到。

不認得的推論端（雲端 API、Ollama）一律回 None，呼叫端退回保守常數。
"""

import time

from loguru import logger

from .model_probe import fetch_lmstudio_models, lmstudio_root

_PROBE_TIMEOUT = 1.5
_RETRY_COOLDOWN = 60.0  # 問不到時，至少隔這麼久才再問一次

# base_url -> window。None 代表問過但問不出來（例如模型還沒載入、端點不存在）。
_cache: dict[str, int] = {}
_last_failed_at: dict[str, float] = {}


def _lmstudio_root(base_url: str) -> str:
    """保留這個名字：既有測試釘著它。實作移到 model_probe，避免兩個地方
    各自知道 /v1 與 /api/v0 的關係。"""
    return lmstudio_root(base_url)


def _probe_lmstudio(base_url: str, model: str | None) -> int | None:
    """回傳目前載入的 context 長度；問不到回 None。

    多個模型同時載入時優先認呼叫端指名的那個——對話用的是哪顆，預算就該照哪顆算。
    """
    loaded = [
        m
        for m in fetch_lmstudio_models(base_url)
        if isinstance(m, dict) and m.get("loaded_context_length")
    ]
    if not loaded:
        return None
    for m in loaded:
        if model and m.get("id") == model:
            return int(m["loaded_context_length"])
    return int(loaded[0]["loaded_context_length"])


def detect_context_window(base_url: str, model: str | None = None) -> int | None:
    """目前載入的 context window（token）；不知道就回 None。

    整段 fail-soft：探測失敗絕不能影響對話，呼叫端退回保守預設就好。
    """
    if not base_url:
        return None
    key = str(base_url)
    if key in _cache:
        return _cache[key]

    last = _last_failed_at.get(key)
    if last is not None and time.monotonic() - last < _RETRY_COOLDOWN:
        return None

    try:
        window = _probe_lmstudio(base_url, model)
    except Exception as e:
        logger.debug(f"[context_window] probe failed for {base_url}: {e}")
        window = None

    if window and window > 0:
        _cache[key] = window
        _last_failed_at.pop(key, None)
        logger.info(f"[context_window] detected {window} tokens at {base_url}")
        return window

    # 模型可能只是還沒載入，晚點會有答案——所以不寫進 _cache，只記冷卻時間。
    _last_failed_at[key] = time.monotonic()
    return None


def reset_cache() -> None:
    """給測試用；也讓換模型後可以重新探測。"""
    _cache.clear()
    _last_failed_at.clear()
