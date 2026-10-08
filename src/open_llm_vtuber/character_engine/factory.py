"""建立引擎那一側（CharacterCompanion）。引擎只在這裡與 agent 裡才被匯入。

AI Character Engine 是選用的：它要 Python 3.11 以上，而這個專案支援 3.10。沒選
character_engine_agent 的人不該因為沒裝它而受任何影響，所以匯入放在函式裡，失敗時
把原因與做法講清楚。
"""

import asyncio
import dataclasses
import functools
import inspect
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from loguru import logger

from ..context_window import cooling_down, detect_context_window
from ..utils.path_safety import safe_join
from ..character_mood import mood_message

# 背景工作要的是穩定的 JSON，不是有個性的對話。只帶「關掉思考模式」這類欄位：
# 沒帶的話每個背景工作都會先思考到逾時（舊的記憶整理出過同一件事）；
# 而對話用的 presence_penalty／repeat_penalty 會懲罰 JSON 裡本來就該重複的鍵名。
REASONING_KEYS = (
    "reasoning_effort",
    "reasoning",
    "chat_template_kwargs",
    "enable_thinking",
    "think",
)
WORKER_TEMPERATURE = 0.1
WORKER_MAX_TOKENS = 600
# 每句的表情與動作（reply_actions）只要一行 JSON；scripts/eval_expression_pick.py 同一組。
PICK_TEMPERATURE = 0
PICK_MAX_TOKENS = 80
# 看圖是回覆之前多出來的一次模型呼叫，越短越好。
EYES_MAX_TOKENS = 160
EYES_PROMPT = "用兩三句話說出畫面裡有什麼。只講看得到的，不要猜測，不要用條列或標記。"
# 問不到 window 時當它有這麼大。引擎預設的 8192 裝不下一份真的人設（Mao 的
# 系統提示約 4500 token），主動發話那一輪會直接失敗。猜大了頂多推論端回錯。
UNKNOWN_WINDOW_TOKENS = 16384
# 問不到 window 就再問幾次（伺服器常比模型早起來），之後放棄：雲端端點或 Ollama
# 永遠答不出來，而問一次是一次同步的網路請求，會把所有連線的語音卡住一下。
WINDOW_PROBES = 5
# 一輪可以包含工具呼叫（搜尋網頁要十幾秒）再加一段長回覆。
TURN_TIMEOUT_SECONDS = 180.0
# 語音對話一句很短，引擎預設的 40 則會太早忘記前面講過的；真的太長的時候引擎
# 會照 token 預算自己挑。
HISTORY_MESSAGES = 80
REPLY_TIMEOUT_SECONDS = 120.0

UNAVAILABLE = (
    "character_engine_agent 需要 AI Character Engine（套件名 ai-character-engine），"
    "它是 Tomoshibi 的依賴，卻沒有裝起來；目前是 Python {python}，引擎要 3.11 以上。\n"
    "做法：在專案目錄執行 uv sync（.python-version 是 3.12，uv 會自己下載）。\n"
    "原始錯誤：{error}"
)
NOT_COMPATIBLE = (
    "character_engine_agent 的對話由引擎直接呼叫模型，目前只支援 OpenAI 相容的端點"
    "（lmstudio_llm、ollama 的 /v1、openai_compatible_llm…），而且要有 base_url 與 "
    "model。目前的 llm_provider 是 {provider}。\n"
    "做法：換一個 OpenAI 相容的 llm_provider（LM Studio、Ollama 的 /v1、"
    "OpenAI 相容 API）。"
)
TOO_OLD = (
    "安裝的 AI Character Engine 太舊：這版 Tomoshibi 要引擎自己記得她說過的話"
    "（ai_character_engine.companion.SELF_MEMORY_LINE），也要她的心情會淡掉"
    "（ai_character_engine.companion.CHARACTER_MOODS，引擎 1.1.0 起）。\n"
    "做法：在專案目錄執行 uv sync 換回 pyproject.toml 釘的那一版。"
)
# 背景工作（情緒、記憶、目標…）另外用的端點。不是引擎的設定，先從設定裡拿出來。
BACKGROUND_KEYS = ("background_base_url", "background_model", "background_api_key")
# conf.yaml 裡的名字 → 引擎的名字
_RENAMED_SETTINGS = {
    "timeout_seconds": "call_timeout_seconds",
    "max_rebase_turns": "max_turns_late",
}


def _known_settings(settings_class: Any, settings: Mapping[str, Any]) -> dict:
    """換成引擎的名字，只留裝的這版引擎認得的。

    conf.yaml 可以比引擎新（reply_check_every 是 1.2.0 才有的）；照傳的話
    CompanionSettings 丟 TypeError，她整個開不起來。少一項設定只是那項沒作用。
    """
    known = {field.name for field in dataclasses.fields(settings_class)}
    out = {}
    for name, value in settings.items():
        name = _RENAMED_SETTINGS.get(name, name)
        if name in known:
            out[name] = value
        else:
            logger.warning(f"[engine] this engine has no setting {name}; left out")
    return out


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


def _clients(
    provider: str,
    llm_config: Mapping[str, Any],
    background: Optional[Mapping[str, Any]] = None,
) -> tuple:
    """(她講話用的, 背景認知用的, 看圖用的, 挑表情用的)。預設同一個端點、同一顆模型，設定不同。

    background 有網址也有模型時，背景認知改用那一個（例如另一台電腦上的模型）：
    她講話時就不用跟背景工作搶同一顆。只填一半就不用，免得拿半套設定去連。
    """
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
    picking = {"temperature": PICK_TEMPERATURE, "max_tokens": PICK_MAX_TOKENS}
    switches = {k: v for k, v in extra_body.items() if k in REASONING_KEYS}
    if switches:
        thinking["extra_body"] = switches
        picking["extra_body"] = dict(switches)

    shared = {
        "model": model,
        "base_url": base_url,
        "api_key": str(llm_config.get("llm_api_key") or "") or None,
        "backend": provider,
    }
    elsewhere = dict(shared)
    background = background or {}
    base = str(background.get("background_base_url") or "").strip()
    other = str(background.get("background_model") or "").strip()
    if base and other:
        elsewhere.update(
            base_url=base,
            model=other,
            api_key=str(background.get("background_api_key") or "")
            or shared["api_key"],
        )
    return (
        _engine_client(
            **shared, timeout_seconds=REPLY_TIMEOUT_SECONDS, request_options=talking
        ),
        # 逾時由引擎的背景排程自己管。
        _engine_client(**elsewhere, timeout_seconds=None, request_options=thinking),
        _vision(provider, llm_config, thinking),
        # 跟背景工作同一個端點；逾時由引擎的 actions_timeout_seconds 管。
        _engine_client(**elsewhere, timeout_seconds=None, request_options=picking),
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
    probes: int = 0


def _fit_the_window(live: _Live) -> None:
    """伺服器常比模型早起來，那時問不到 window。之後再問幾次，問到了就換預算。"""
    from ai_character_engine.context.budget import ContextBudget

    if live.window or live.probes >= WINDOW_PROBES:
        return
    if cooling_down(live.base_url):
        # 問不到之後一分鐘內不會真的去問；那些呼叫不算一次。
        return
    live.probes += 1
    window = detect_context_window(live.base_url, live.model)
    if window:
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

# 誰在聽哪個角色的心情（鍵同 _LIVE）。記在鍵上而不是 companion 上：存設定會換一個
# companion，頁面不必因此重新連線。
_MOOD_LISTENERS: dict[str, list] = {}


def listen_to_mood(key: str, listener: Callable[[dict], None]) -> Callable[[], None]:
    """背景結果改了這個角色的心情時呼叫 listener(訊息)。回傳停止聽的函式。"""
    listeners = _MOOD_LISTENERS.setdefault(key, [])
    listeners.append(listener)

    def stop() -> None:
        if listener in listeners:
            listeners.remove(listener)

    return stop


def _tell_mood(key: str, snapshot: Any) -> None:
    message = mood_message(snapshot)
    if message is None:
        return
    for listener in list(_MOOD_LISTENERS.get(key, ())):
        try:
            listener(message)
        except Exception as error:
            # 一個關掉的頁面不能讓其他頁面收不到。
            logger.debug(f"[mood] listener failed ({type(error).__name__}: {error})")


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
    persona: str = "",
) -> str:
    """確保這個角色有一個符合目前設定的 companion，回傳用來查它的鍵。

    language 是她回話用的語言。記憶、目標、體會也用它寫：不講的話模型得自己從
    對話看出來，而它不一定看得出來。

    persona 是她的人設原文（character_config.persona_prompt，逐字，不含共用規則
    與其他附加內容），一字不差地包在 system／description 裡面。放進
    CharacterProfile.background 讓背景工作（情緒、心情…）讀得到她是誰；description
    已經包含它，引擎的 ContextBuilder 看到 background 是 description 的子字串就不會
    另外印一段 Background，她自己的對話提示不會因此多出東西。

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
    # 舊版引擎收到它不認得的設定（self_memory_every）只會丟一個看不懂的 TypeError，
    # 或少了主機已經不再自己做的檢查。SELF_MEMORY_LINE 跟這裡用到的其他新東西
    # （speak_up 的 statement_only、from_before、引擎那一側的輸出檢查）同一版起才有；
    # CHARACTER_MOODS（1.1.0 起，她的心情）也一樣。
    import ai_character_engine.companion as engine_companion

    if not hasattr(engine_companion, "SELF_MEMORY_LINE") or not hasattr(
        engine_companion, "CHARACTER_MOODS"
    ):
        raise RuntimeError(TOO_OLD)

    settings = dict(settings or {})
    background = {
        name: settings.pop(name) for name in BACKGROUND_KEYS if name in settings
    }
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
            "settings": settings,
            "background": background,
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

    talking, thinking, eyes, picking = _clients(provider, llm_config, background)
    # 引擎 1.3.0 起挑表情可以有自己的 client；更舊的沒有這個參數。
    extra = (
        {"actions_llm": picking}
        if "actions_llm" in inspect.signature(CharacterCompanion).parameters
        else {}
    )
    if live:
        _let_go(live.companion)
    companion = CharacterCompanion(
        character=CharacterProfile(
            id=conf_uid,
            name=character_name or conf_uid,
            description=system,
            background=persona or None,
        ),
        llm=talking,
        background_llm=thinking,
        storage_dir=directory,
        settings=CompanionSettings(
            **{
                "max_history_messages": HISTORY_MESSAGES,
                "language": language,
                **_known_settings(CompanionSettings, settings),
            }
        ),
        context_builder=ContextBuilder(budget=budget),
        vision=eyes,
        bridge_config=HostBridgeConfig(turn_timeout_seconds=TURN_TIMEOUT_SECONDS),
        **extra,
    )
    # 背景結果改了她的心情：告訴正在看這個角色的每個頁面。
    companion.on_mood_change = functools.partial(_tell_mood, key)
    _LIVE[key] = _Live(
        signature,
        companion,
        base_url=str(llm_config.get("base_url") or ""),
        model=str(llm_config.get("model") or ""),
        window=window,
        probes=1,
    )
    logger.info(f"[engine] companion ready for {conf_uid} at {directory}")
    return key
