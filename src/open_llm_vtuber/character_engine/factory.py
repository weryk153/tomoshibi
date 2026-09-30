"""建立引擎那一側（CharacterCompanion）。引擎只在這裡與 agent 裡才被匯入。

AI Character Engine 是選用的：它要 Python 3.11 以上，而這個專案支援 3.10。沒選
character_engine_agent 的人不該因為沒裝它而受任何影響，所以匯入放在函式裡，失敗時
把原因與做法講清楚。
"""

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from loguru import logger

from ..context_window import detect_context_window
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
# 看圖是回覆之前多出來的一次模型呼叫，越短越好。
EYES_MAX_TOKENS = 160
EYES_PROMPT = "用兩三句話說出畫面裡有什麼。只講看得到的，不要猜測，不要用條列或標記。"
# 問不到 window 時當它有這麼大。引擎預設的 8192 裝不下一份真的人設（Mao 的
# 系統提示約 4500 token），主動發話那一輪會直接失敗。猜大了頂多推論端回錯。
UNKNOWN_WINDOW_TOKENS = 16384
# 一輪可以包含工具呼叫（搜尋網頁要十幾秒）再加一段長回覆。
TURN_TIMEOUT_SECONDS = 180.0
# basic_memory_agent 留 20000 字、至少 24 則。語音對話一句很短，引擎預設的 40 則
# 會比原本更早忘記前面講過的；真的太長的時候引擎會照 token 預算自己挑。
HISTORY_MESSAGES = 80
REPLY_TIMEOUT_SECONDS = 120.0

UNAVAILABLE = (
    "character_engine_agent 需要 AI Character Engine（套件名 ai-character-engine），"
    "而它要 Python 3.11 以上；目前是 Python {python}。\n"
    "做法：用 3.11 或 3.12 建環境（uv sync --python 3.12），再把引擎裝進去"
    "（uv pip install <引擎的路徑或 wheel>）。\n"
    "或者把 conf.yaml 的 conversation_agent_choice 改回 basic_memory_agent。\n"
    "原始錯誤：{error}"
)
NOT_COMPATIBLE = (
    "character_engine_agent 的對話由引擎直接呼叫模型，目前只支援 OpenAI 相容的端點"
    "（lmstudio_llm、ollama 的 /v1、openai_compatible_llm…），而且要有 base_url 與 "
    "model。目前的 llm_provider 是 {provider}。\n"
    "做法：換一個 OpenAI 相容的 llm_provider，或把 conversation_agent_choice 改回 "
    "basic_memory_agent。"
)
# conf.yaml 裡的名字 → 引擎的名字
_RENAMED_SETTINGS = {
    "timeout_seconds": "call_timeout_seconds",
    "max_rebase_turns": "max_turns_late",
}


def _engine_client(**options):
    from ai_character_engine.llm.local import OpenAICompatibleChatClient

    return OpenAICompatibleChatClient(**options)


def _engine_eyes(**options):
    from ai_character_engine.vision.providers import OpenAICompatibleVisionProvider

    return OpenAICompatibleVisionProvider(**options)


def _vision(provider: str, llm_config: Mapping[str, Any], thinking_options: dict):
    """用同一顆模型看圖。引擎的訊息只有文字：圖先被描述成文字，她讀到的是描述。"""
    from ai_character_engine.vision import VisionPipeline
    from ai_character_engine.vision.sampling import FrameGate

    return VisionPipeline(
        provider=_engine_eyes(
            model=str(llm_config.get("model")),
            base_url=str(llm_config.get("base_url")),
            api_key=str(llm_config.get("llm_api_key") or "") or None,
            provider=provider,
            request_options={**thinking_options, "max_tokens": EYES_MAX_TOKENS},
            default_prompt=EYES_PROMPT,
        ),
        # 鏡頭每一輪都送畫面來，常常是同一張；引擎預設會擋掉重複的畫面，
        # 而一輪的畫面全被擋掉時那一輪會失敗。
        frame_gate=FrameGate(min_interval_seconds=0, deduplicate=False),
    )


def _clients(provider: str, llm_config: Mapping[str, Any]) -> tuple:
    """(她講話用的, 背景認知用的, 看圖用的)。同一個端點、同一顆模型，設定不同。"""
    base_url = str(llm_config.get("base_url") or "").strip()
    model = str(llm_config.get("model") or "").strip()
    if provider == "claude_llm" or not base_url or not model:
        raise ValueError(NOT_COMPATIBLE.format(provider=provider))

    extra_body = dict(llm_config.get("extra_body") or {})
    talking = {}
    if llm_config.get("temperature") is not None:
        talking["temperature"] = llm_config["temperature"]
    if extra_body:
        talking["extra_body"] = extra_body
    thinking = {"temperature": WORKER_TEMPERATURE, "max_tokens": WORKER_MAX_TOKENS}
    switches = {k: v for k, v in extra_body.items() if k in _REASONING_KEYS}
    if switches:
        thinking["extra_body"] = switches

    shared = {
        "model": model,
        "base_url": base_url,
        "api_key": str(llm_config.get("llm_api_key") or "") or None,
        "backend": provider,
    }
    return (
        _engine_client(
            **shared, timeout_seconds=REPLY_TIMEOUT_SECONDS, request_options=talking
        ),
        # 逾時由引擎的背景排程自己管。
        _engine_client(**shared, timeout_seconds=None, request_options=thinking),
        _vision(provider, llm_config, thinking),
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
    companion: Any
    base_url: str = ""
    model: str = ""
    window: Optional[int] = None


def _fit_the_window(live: _Live) -> None:
    """伺服器常比模型早起來，那時問不到 window。之後每一輪都來問，問到了就換預算。"""
    from ai_character_engine.context.budget import ContextBudget

    window = detect_context_window(live.base_url, live.model)
    if window and window != live.window:
        live.window = window
        live.companion.runtime.context_builder.budget = ContextBudget(
            context_window_tokens=window
        )


# 每個角色同一時間只有一個 companion，所有 agent 共用。
#
# 每次儲存設定都會重建 agent（reload-config → init_agent），切角色再切回來也是；
# 各自建一個的話，它們會寫同一個資料夾、互相蓋掉狀態。所以 agent 不自己拿著它，
# 每次都來這裡問「現在是哪一個」。
_LIVE: dict[str, _Live] = {}
_CLOSING: set = set()


def current_companion(key: str) -> Optional[Any]:
    live = _LIVE.get(key)
    if live is None:
        return None
    _fit_the_window(live)
    return live.companion


def _let_go(companion: Any) -> None:
    """先讓舊的存最後一次檔並停手，新的才讀得到完整的狀態；收尾之後再做。"""
    companion.retire()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(_release(companion))
    _CLOSING.add(task)
    task.add_done_callback(_CLOSING.discard)


async def _release(companion: Any) -> None:
    try:
        # retire() 讓她把正在講的那句講完；close() 會切斷它。一輪最久就是
        # TURN_TIMEOUT_SECONDS，等超過的話那一輪是卡住了。
        waited = 0.0
        while companion.busy and waited < TURN_TIMEOUT_SECONDS:
            await asyncio.sleep(0.2)
            waited += 0.2
        await companion.close()
    except Exception as exc:
        # 它可能屬於另一個已經結束的 event loop；狀態在 retire() 時已經存好了。
        logger.debug(f"[engine] old companion not released ({type(exc).__name__})")


def build_companion(
    *,
    conf_uid: str,
    character_name: str,
    system: str,
    provider: str,
    llm_config: Mapping[str, Any],
    settings: Optional[Mapping[str, Any]] = None,
    language: str = "",
) -> str:
    """確保這個角色有一個符合目前設定的 companion，回傳用來查它的鍵。

    language 是她回話用的語言。記憶、目標、體會也用它寫：不講的話模型得自己從
    對話看出來，而它不一定看得出來。

    人設（system）不算在「設定」裡：它每輪都可能刷新，由 agent 直接改她的描述。
    """
    try:
        from ai_character_engine import CharacterProfile
        from ai_character_engine.companion import (
            CharacterCompanion,
            CompanionSettings,
        )
        from ai_character_engine.context.budget import ContextBudget
        from ai_character_engine.context.builder import ContextBuilder
        from ai_character_engine.host import HostBridgeConfig
    except ImportError as exc:
        raise RuntimeError(
            UNAVAILABLE.format(python=sys.version.split()[0], error=exc)
        ) from exc

    directory = storage_dir(conf_uid)
    key = str(directory.resolve())
    window = detect_context_window(
        str(llm_config.get("base_url") or ""), str(llm_config.get("model") or "")
    )
    signature = json.dumps(
        {
            "character_name": character_name,
            "provider": provider,
            "llm": {
                name: llm_config.get(name)
                for name in (
                    "base_url",
                    "model",
                    "llm_api_key",
                    "temperature",
                    "extra_body",
                )
            },
            "settings": dict(settings or {}),
            "language": language,
        },
        sort_keys=True,
        default=str,
    )
    budget = ContextBudget(context_window_tokens=window or UNKNOWN_WINDOW_TOKENS)
    live = _LIVE.get(key)
    if live and live.signature == signature and live.companion.usable_in_running_loop():
        _fit_the_window(live)
        return key

    talking, thinking, eyes = _clients(provider, llm_config)
    if live:
        _let_go(live.companion)
    _LIVE[key] = _Live(
        signature,
        CharacterCompanion(
            character=CharacterProfile(
                id=conf_uid, name=character_name or conf_uid, description=system
            ),
            llm=talking,
            background_llm=thinking,
            storage_dir=directory,
            settings=CompanionSettings(
                **{
                    "max_history_messages": HISTORY_MESSAGES,
                    "language": language,
                    **{
                        _RENAMED_SETTINGS.get(name, name): value
                        for name, value in dict(settings or {}).items()
                    },
                }
            ),
            context_builder=ContextBuilder(budget=budget),
            vision=eyes,
            bridge_config=HostBridgeConfig(turn_timeout_seconds=TURN_TIMEOUT_SECONDS),
        ),
        base_url=str(llm_config.get("base_url") or ""),
        model=str(llm_config.get("model") or ""),
        window=window,
    )
    logger.info(f"[engine] companion ready for {conf_uid} at {directory}")
    return key
