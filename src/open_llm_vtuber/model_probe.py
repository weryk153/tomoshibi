"""問本機推論端有哪些模型，正規化成同一種型別。

這層只做翻譯。它不決定任何設定（那是 model_profiles 的事），也不寫任何檔案
（那是 write_provider_config 的事）。分開的理由是三者的變更頻率完全不同：端點
形狀跟著推論端改版走、必要設定跟著模型家族走、寫入規則跟著 conf.yaml 結構走。

與 context_window 的關係：兩者都打 LM Studio 的 /api/v0/models，但用途不同——
context_window 是執行期問「目前載入的 window 多大」（懶惰、有快取與冷卻），
這裡是設定期問「有哪些模型」。共用 fetch_lmstudio_models 這層 HTTP + 解析，
避免兩個地方各自知道端點形狀；快取與冷卻的語意留在 context_window。
"""

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

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


def fetch_lmstudio_models(base_url: str, timeout: float = _TIMEOUT) -> list[dict]:
    """打 /api/v0/models，回原始的 data 陣列。失敗丟例外，由呼叫端決定怎麼降級。

    timeout：
      - 預設 3.0s（設定期，使用者願意等）
      - context_window 呼叫時傳 1.5s（對話路徑上，同步在事件迴圈，要快速失敗）
    """
    url = f"{lmstudio_root(base_url)}/api/v0/models"
    with httpx.Client(timeout=timeout) as client:
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


def probe_lmstudio(base_url: str) -> tuple[bool, list[DetectedModel]]:
    """探測 LM Studio，回傳 (可達, 模型清單) 兩件分開的事。

    「連得上但一顆模型都沒下載」跟「連不上」都會讓模型清單是空的，但對使用者
    該給的建議完全不同——前者是「去下載一個模型」，後者是「去把 LM Studio
    打開」。這兩者以前被 list_lmstudio_models() 折疊成同一個空清單，呼叫端
    （detect 端點）拿 bool(models) 當「LM Studio 可用」的訊號，結果永遠分不出
    這兩種情況（見 tomoshibi 這次修的 bug：first-run-model-detection Task 9）。
    fetch_lmstudio_models() 連不上時丟例外，這裡把它接住並轉成
    reachable=False，而不是讓兩種情況都變成「回空清單」。
    """
    try:
        raw_list = fetch_lmstudio_models(base_url)
    except Exception as e:
        logger.debug(f"[model_probe] LM Studio probe failed at {base_url}: {e}")
        return False, []
    out = []
    for raw in raw_list:
        entry = _lmstudio_entry(raw, base_url)
        if entry is not None:
            out.append(entry)
    return True, out


def list_lmstudio_models(base_url: str) -> list[DetectedModel]:
    """LM Studio 上可用於對話的模型。連不上或連得上但沒有模型都回空清單。

    只要模型清單、不在乎可不可達的呼叫端用這個（例如 apply-detected 要重新
    核對使用者選的模型是否還在）。要分辨「連不上」跟「可達但沒模型」的呼叫端
    （例如 detect 端點）改用 probe_lmstudio()，不要在這個函式的空清單結果上
    自己猜原因。
    """
    return probe_lmstudio(base_url)[1]


def ollama_root(base_url: str) -> str:
    """Ollama 原生 API 的根位址。設定裡寫的是 .../v1（OpenAI 相容那套），
    而 /api/tags 與 /api/show 在 /v1 之外。"""
    return base_url.rstrip("/").removesuffix("/v1")


def fetch_ollama_tags(base_url: str) -> list[dict]:
    """打 /api/tags，回原始的 models 陣列。失敗丟例外。"""
    url = f"{ollama_root(base_url)}/api/tags"
    with httpx.Client(timeout=_TIMEOUT) as client:
        payload = client.get(url).json()
    models = payload.get("models")
    return models if isinstance(models, list) else []


def fetch_ollama_show(base_url: str, model_id: str) -> dict:
    """打 /api/show 拿單一模型的細節。失敗丟例外。"""
    url = f"{ollama_root(base_url)}/api/show"
    with httpx.Client(timeout=_TIMEOUT) as client:
        return client.post(url, json={"model": model_id}).json()


def ollama_installed() -> bool:
    """這台電腦上有沒有裝 Ollama，跟它有沒有在跑無關。

    連不上 11434 時，「沒裝」和「裝了但沒開」要給的建議不同：前者要下載連結，
    後者只要打開 app。精靈原本一律顯示「請先安裝」，已經裝好只是沒開的人會以為
    自己裝失敗了。

    只看常見的安裝位置，找不到就當沒裝——最壞情況是多顯示一個下載連結，不會
    擋住任何事。
    """
    if shutil.which("ollama"):
        return True
    candidates: list[Path] = []
    if sys.platform == "darwin":
        candidates += [
            Path("/Applications/Ollama.app"),
            Path.home() / "Applications" / "Ollama.app",
        ]
    elif sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidates.append(Path(local) / "Programs" / "Ollama" / "ollama app.exe")
            candidates.append(Path(local) / "Programs" / "Ollama" / "ollama.exe")
    return any(c.exists() for c in candidates)


def probe_ollama(base_url: str) -> tuple[bool, list[DetectedModel]]:
    """探測 Ollama，回傳 (可達, 模型清單)。語意同 probe_lmstudio()——可達性跟
    有沒有模型是兩件事，呼叫端不該用模型清單是不是空的去猜可達性。

    只回名字——能力要逐顆問 /api/show，二十顆模型就是二十次請求，所以留到
    使用者選定之後（見 describe_ollama_model）。
    """
    try:
        raw_list = fetch_ollama_tags(base_url)
    except Exception as e:
        logger.debug(f"[model_probe] Ollama probe failed at {base_url}: {e}")
        return False, []
    out = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
        out.append(
            DetectedModel(
                id=name,
                backend="ollama",
                base_url=base_url,
                arch=(
                    str(details["family"]).strip() if details.get("family") else None
                ),
            )
        )
    return True, out


def list_ollama_models(base_url: str) -> list[DetectedModel]:
    """Ollama 上有哪些模型。連不上或連得上但沒有模型都回空清單。

    只要模型清單、不在乎可不可達的呼叫端用這個。要分辨「連不上」跟「可達但
    沒模型」改用 probe_ollama()——理由同 list_lmstudio_models()。
    """
    return probe_ollama(base_url)[1]


def _ollama_context_length(model_info: dict, arch: str | None) -> int | None:
    """model_info 的 context 鍵是 '<arch>.context_length'，不是固定名字。

    優先用 arch 組出來的鍵；arch 不明或對不上時退而找任何以 .context_length
    結尾的鍵——只認固定名字的話，換個模型家族就抓不到。
    """
    if arch:
        value = model_info.get(f"{arch}.context_length")
        if isinstance(value, int):
            return value
    for key, value in model_info.items():
        if key.endswith(".context_length") and isinstance(value, int):
            return value
    return None


def describe_ollama_model(base_url: str, model_id: str) -> DetectedModel | None:
    """補上這顆模型的能力資訊。問不到回 None，呼叫端沿用列表階段那筆。"""
    try:
        payload = fetch_ollama_show(base_url, model_id)
    except Exception as e:
        logger.debug(f"[model_probe] Ollama show failed for {model_id}: {e}")
        return None
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    caps = payload.get("capabilities")
    caps = caps if isinstance(caps, list) else []
    model_info = (
        payload.get("model_info") if isinstance(payload.get("model_info"), dict) else {}
    )
    arch = str(details["family"]).strip() if details.get("family") else None
    return DetectedModel(
        id=model_id,
        backend="ollama",
        base_url=base_url,
        arch=arch,
        is_vlm=("vision" in caps),
        supports_tools=("tools" in caps),
        max_context=_ollama_context_length(model_info, arch),
        quantization=(
            str(details["quantization_level"]).strip()
            if details.get("quantization_level")
            else None
        ),
    )
