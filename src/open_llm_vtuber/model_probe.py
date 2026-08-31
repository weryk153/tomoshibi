"""問本機推論端有哪些模型，正規化成同一種型別。

這層只做翻譯。它不決定任何設定（那是 model_profiles 的事），也不寫任何檔案
（那是 write_provider_config 的事）。分開的理由是三者的變更頻率完全不同：端點
形狀跟著推論端改版走、必要設定跟著模型家族走、寫入規則跟著 conf.yaml 結構走。

與 context_window 的關係：兩者都打 LM Studio 的 /api/v0/models，但用途不同——
context_window 是執行期問「目前載入的 window 多大」（懶惰、有快取與冷卻），
這裡是設定期問「有哪些模型」。共用 fetch_lmstudio_models 這層 HTTP + 解析，
避免兩個地方各自知道端點形狀；快取與冷卻的語意留在 context_window。
"""

from dataclasses import dataclass

import httpx
from loguru import logger

_TIMEOUT = 3.0

# 能拿來對話的類型。embeddings 之類的列出來只會讓使用者選錯。
_CHAT_TYPES = frozenset({"llm", "vlm"})


@dataclass(frozen=True)
class DetectedModel:
    id: str
    backend: str  # 'lmstudio' | 'ollama' → 決定寫哪個 conf 區塊
    base_url: str
    arch: str | None = None
    is_vlm: bool = False
    supports_tools: bool = False
    max_context: int | None = None
    quantization: str | None = None


def lmstudio_root(base_url: str) -> str:
    """把 OpenAI 相容的 base_url 還原成 LM Studio 的根位址。

    設定裡寫的是 'http://127.0.0.1:1234/v1'，而 /api/v0 跟 /v1 是平行的兩套。
    """
    return base_url.rstrip("/").removesuffix("/v1")


def fetch_lmstudio_models(base_url: str) -> list[dict]:
    """打 /api/v0/models，回原始的 data 陣列。失敗丟例外，由呼叫端決定怎麼降級。"""
    url = f"{lmstudio_root(base_url)}/api/v0/models"
    with httpx.Client(timeout=_TIMEOUT) as client:
        payload = client.get(url).json()
    data = payload.get("data")
    return data if isinstance(data, list) else []


def _lmstudio_entry(raw: dict, base_url: str) -> DetectedModel | None:
    if not isinstance(raw, dict):
        return None
    model_id = str(raw.get("id") or "").strip()
    kind = str(raw.get("type") or "").strip().lower()
    if not model_id or kind not in _CHAT_TYPES:
        return None
    caps = raw.get("capabilities")
    caps = caps if isinstance(caps, list) else []
    max_context = raw.get("max_context_length")
    return DetectedModel(
        id=model_id,
        backend="lmstudio",
        base_url=base_url,
        arch=(str(raw["arch"]).strip() if raw.get("arch") else None),
        is_vlm=(kind == "vlm"),
        supports_tools=("tool_use" in caps),
        max_context=(int(max_context) if isinstance(max_context, int) else None),
        quantization=(
            str(raw["quantization"]).strip() if raw.get("quantization") else None
        ),
    )


def list_lmstudio_models(base_url: str) -> list[DetectedModel]:
    """LM Studio 上可用於對話的模型。連不上就回空清單。

    fail-soft 是刻意的：連不上不是錯誤，是「這個後端現在沒有模型」。首次啟動
    精靈不能因為使用者沒裝 LM Studio 就壞掉。
    """
    try:
        raw_list = fetch_lmstudio_models(base_url)
    except Exception as e:
        logger.debug(f"[model_probe] LM Studio probe failed at {base_url}: {e}")
        return []
    out = []
    for raw in raw_list:
        entry = _lmstudio_entry(raw, base_url)
        if entry is not None:
            out.append(entry)
    return out
