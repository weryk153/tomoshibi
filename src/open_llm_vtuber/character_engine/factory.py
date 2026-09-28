"""建立認知工作階段。引擎只在這裡才被匯入。

AI Character Engine 是選用的：它要 Python 3.11 以上，而這個專案支援 3.10。沒選
character_engine_agent 的人不該因為沒裝它而受任何影響，所以匯入放在函式裡，失敗時
把原因與做法講清楚。
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from loguru import logger

from ..utils.path_safety import safe_join

# 背景工作要的是穩定的 JSON，不是有個性的對話。只帶「關掉思考模式」這類欄位：
# 沒帶的話每個背景工作都會先思考到逾時（memory_core._request_rewrite 出過同一件事）；
# 而對話用的 presence_penalty／repeat_penalty 會懲罰 JSON 裡本來就該重複的鍵名。
_REASONING_KEYS = (
    "reasoning_effort",
    "reasoning",
    "chat_template_kwargs",
    "enable_thinking",
    "think",
)
WORKER_TEMPERATURE = 0.1
WORKER_MAX_TOKENS = 600

UNAVAILABLE = (
    "character_engine_agent 需要 AI Character Engine（套件名 ai-character-engine），"
    "而它要 Python 3.11 以上；目前是 Python {python}。\n"
    "做法：用 3.11 或 3.12 建環境（uv sync --python 3.12），再把引擎裝進去"
    "（uv pip install <引擎的路徑或 wheel>）。\n"
    "或者把 conf.yaml 的 conversation_agent_choice 改回 basic_memory_agent。\n"
    "原始錯誤：{error}"
)


def _worker_client(provider: str, llm_config: Mapping[str, Any]) -> Optional[Any]:
    from ai_character_engine.llm.local import OpenAICompatibleChatClient

    base_url = str(llm_config.get("base_url") or "").strip()
    model = str(llm_config.get("model") or "").strip()
    if provider == "claude_llm" or not base_url or not model:
        logger.warning(
            f"[engine] {provider} 不是 OpenAI 相容的端點，背景認知停用；對話不受影響。"
        )
        return None
    extra_body = {
        key: value
        for key, value in dict(llm_config.get("extra_body") or {}).items()
        if key in _REASONING_KEYS
    }
    options = {"temperature": WORKER_TEMPERATURE, "max_tokens": WORKER_MAX_TOKENS}
    if extra_body:
        options["extra_body"] = extra_body
    return OpenAICompatibleChatClient(
        model=model,
        base_url=base_url,
        api_key=str(llm_config.get("llm_api_key") or "") or None,
        backend=provider,
        timeout_seconds=None,  # 逾時由背景工作自己的 timeout_seconds 管
        request_options=options,
    )


def storage_dir(conf_uid: str) -> Path:
    """chat_history/<conf_uid>/engine。

    conf_uid 的清理方式跟 chat_history_manager 一樣（取 basename），不然同一個角色的
    歷史在一個資料夾、引擎狀態在另一個。那一套清理會放過 "." 與 ".."，所以這裡
    另外擋掉：chat_history/../engine 是專案根目錄底下的資料夾。
    """
    from ..chat_history_manager import _sanitize_path_component

    name = _sanitize_path_component(conf_uid)
    if not name.strip(". "):
        raise ValueError(f"conf_uid is not a usable folder name: {conf_uid!r}")
    return Path(safe_join("chat_history", name, "engine"))


@dataclass
class _Live:
    signature: str
    session: Any


# 每個角色同一時間只有一個工作階段，所有 agent 共用。
#
# 每次儲存設定都會重建 agent（reload-config → init_agent），切角色再切回來也是；
# 各自建一個工作階段的話，它們會寫同一個資料夾、互相蓋掉狀態。所以 agent 不自己
# 拿著工作階段，每次都來這裡問「現在是哪一個」。
_LIVE: dict[str, _Live] = {}


def current_session(key: str) -> Optional[Any]:
    live = _LIVE.get(key)
    return live.session if live else None


def build_session(
    *,
    conf_uid: str,
    character_name: str,
    provider: str,
    llm_config: Mapping[str, Any],
    settings: Optional[Mapping[str, Any]] = None,
) -> str:
    """確保這個角色有一個符合目前設定的工作階段，回傳用來查它的鍵。"""
    try:
        import ai_character_engine  # noqa: F401

        from .session import CognitionSession, CognitionSettings
    except ImportError as exc:
        raise RuntimeError(
            UNAVAILABLE.format(python=sys.version.split()[0], error=exc)
        ) from exc

    directory = storage_dir(conf_uid)
    key = str(directory.resolve())
    signature = json.dumps(
        {
            "character_name": character_name,
            "provider": provider,
            "llm": {
                name: llm_config.get(name)
                for name in ("base_url", "model", "llm_api_key", "extra_body")
            },
            "settings": dict(settings or {}),
        },
        sort_keys=True,
        default=str,
    )
    live = _LIVE.get(key)
    if live and live.signature == signature and live.session.usable_in_running_loop():
        return key
    if live:
        # 設定變了。先讓舊的存最後一次檔並停手，新的才讀得到完整的狀態。
        live.session.retire()

    client = _worker_client(provider, llm_config)
    _LIVE[key] = _Live(
        signature,
        CognitionSession(
            storage_dir=directory,
            character_id=conf_uid,
            character_name=character_name,
            client_for_role=lambda role: client,
            settings=CognitionSettings(**dict(settings or {})),
        ),
    )
    return key
