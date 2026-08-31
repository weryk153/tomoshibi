"""跨語言語音與翻譯字幕的設定端點。

同一段回覆有兩條可以各自獨立翻譯的路，這是理解這個模組的關鍵：

- **語音**（translate_audio）：回覆先翻成目標語言，再交給 TTS 唸出來。她的聲音
  講的是譯文。
- **字幕**（translate_subtitle + subtitle_target_lang）：另外翻一份，只給畫面看。
  **正典的回覆文字永遠不會被改動**——記憶與對話紀錄用的是原文，所以她「記得」的
  始終是自己人設語言裡的那句話。

兩條路互不相干：可以只翻語音、只翻字幕、都翻、或都不翻。用 llm 引擎且兩邊都開
（目標語言又不同）的話，每一句會被翻兩次，延遲大約加倍；deeplx 快很多。UI 上有
把這件事講清楚。

寫入的兩個鐵則：

1. **就地改行，不重新序列化。** conf.yaml 滿是使用者寫的註解，整份 re-dump 會把
   True 正規化成 true、把註解洗掉。ruamel 只拿來驗證結構，不拿來寫。
2. **絕不刪掉供應商子區塊。** Pydantic 的驗證器要求 translate_audio 為真時，對應
   的 llm／deeplx／tencent 區塊必須存在。清空它等於埋一顆下次開機才爆的雷。

生效時機：conf.yaml 在開機時讀一次，但翻譯引擎會在每次（重新）選擇角色時由
init_translate 重建。所以誠實的說法是——重選角色就會套用，重啟一定套用。回應固定
帶 restart_required，那是安全的底線。
"""

import re
import time
import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from loguru import logger

from .api_guard import (
    is_trusted_request as _is_local_request,
    forbidden as _forbidden,
    make_yaml as _make_yaml,
)
from .conf_editor import (
    block_extent,
    read_conf_lines as _read_conf_lines,
    rewrite_bool_leaf as _rewrite_bool_leaf,
    upsert_leaf,
    rewrite_str_leaf as _rewrite_leaf,
    write_conf as _write_conf,
)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

CONF_PATH = "conf.yaml"

# 預設的日語嗓音。翻譯本身不再設定嗓音——那是角色管理的事——這個值只拿來當
# voice in Character Manager decides spoken language); this is still surfaced in GET as
# an informational hint ("default_jp_voice") only.
DEFAULT_JP_VOICE = "ja-JP-NanamiNeural"
# 語音代號的字元規則。留著當參考，這條路現在不驗證也不設定嗓音了。.
VOICE_SHORTNAME_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")

VALID_ENGINES = {"llm", "deeplx"}
DEFAULT_DEEPLX_ENDPOINT = "http://localhost:1188/v2/translate"
DEFAULT_DEEPLX_TARGET = "JA"
DEFAULT_LLM_TARGET = "日文"


# --- 讀設定 ----------------------------------------------------------------- #


def _load_conf() -> Any:
    yaml = _make_yaml()
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        return yaml.load(f)


def _get_translator_block(data: Any) -> Optional[Any]:
    try:
        return data["character_config"]["tts_preprocessor_config"]["translator_config"]
    except (KeyError, TypeError):
        return None


def _get_edge_tts_voice(data: Any) -> Optional[str]:
    try:
        voice = data["character_config"]["tts_config"]["edge_tts"]["voice"]
        return str(voice) if voice is not None else None
    except (KeyError, TypeError):
        return None


def _get_openai_llm(data: Any) -> Optional[Any]:
    """目前啟用中那個 LLM 供應商的設定區塊。

    必須跟著 basic_memory_agent.llm_provider 走，不能寫死讀 openai_compatible_llm。
    實測過的後果：使用者用 LM Studio，存一次翻譯設定就被改成 Ollama 的端點與模型
    ——翻譯從此連到一個沒在跑的服務，而且 conf.yaml 裡原本正確的值被覆蓋掉了。

    記憶整理那條路犯過一模一樣的錯（resolve_consolidation_llm 已修）。凡是要沿用
    「玩家設好的 LLM」的地方，都要問當前供應商是誰。
    """
    try:
        agent = data["character_config"]["agent_config"]
        provider = agent["agent_settings"]["basic_memory_agent"]["llm_provider"]
        block = agent["llm_configs"].get(provider)
        if block is not None:
            return block
    except (KeyError, TypeError):
        pass
    # 讀不到啟用中的供應商時退回這個區塊——它是絕大多數設定檔都有的那一個。
    try:
        return data["character_config"]["agent_config"]["llm_configs"][
            "openai_compatible_llm"
        ]
    except (KeyError, TypeError):
        return None


def _derive_llm_endpoint(base_url: Optional[str]) -> Optional[str]:
    """把供應商的 base_url 補成完整的 chat/completions 端點。

    LLMTranslate 是直接 POST 到完整網址的，它不會自己接路徑（見
    llm_translate.py），所以在這裡補齊。
    """
    if not base_url:
        return None
    b = str(base_url).rstrip("/")
    if b.endswith("/chat/completions"):
        return b
    return b + "/chat/completions"


# Translation-test sample + verdict. Kept at module level, out of the route
# closure, so the rule that actually matters can be tested without a live LLM.
#
# 一句短、明確、任何語言都能翻的句子。太長會拖慢測試；太短（例如單字）又可能
# 翻出跟原文一樣的結果，讓 unchanged 判斷失準。
TRANSLATOR_TEST_SAMPLE = "今天天氣很好，我們出去走走吧。"


def classify_translation_test(sample: str, result: str) -> tuple[bool, str]:
    """Decide whether a translation attempt actually did anything.

    LLMTranslate swallows every failure — a reasoning model that leaves
    `content` empty, a timeout, a wrong endpoint or model — and returns its
    input verbatim. So "output equals input" is the ONLY signal a caller gets
    that translation did not happen; without this check a broken translator
    reports success and the character just speaks untranslated text.

    Returns (ok, reason).
    """
    unchanged = str(result or "").strip() == str(sample or "").strip()
    return (not unchanged, "unchanged" if unchanged else "ok")


# --------------------------------------------------------------------------- #
# --- 寫設定（就地改行，保留註解）------------------------------------------- #
# --------------------------------------------------------------------------- #


def _quote_yaml_scalar(value: str) -> str:
    """YAML 的單引號純量；內部的單引號要成對跳脫。"""
    return "'" + str(value).replace("'", "''") + "'"


def _validate_translator_path() -> None:
    """結構不對就在動手之前失敗，不要留下改到一半的設定檔。"""
    data = _load_conf()
    if _get_translator_block(data) is None:
        raise KeyError(
            "translator_config block not found in conf.yaml "
            "(character_config.tts_preprocessor_config.translator_config)"
        )


def _nested(block: Any, name: str, key: str, default: str = "") -> str:
    """讀 translator_config 底下某個子區塊的一個值；缺任何一層都回預設值。

    子區塊可能整個不存在（使用者刪掉了、或用的是舊範本），所以每一層都要能落空。
    """
    try:
        sub = block.get(name)
        value = sub.get(key) if sub is not None else None
        return str(value) if value is not None else default
    except Exception:
        return default


def _stored_subtitle_target() -> str:
    """目前存著的字幕目標語言；讀不到就空字串。"""
    try:
        block = _get_translator_block(_load_conf())
        value = block.get("subtitle_target_lang") if block else None
        return str(value).strip() if value else ""
    except Exception:
        return ""


def _subtitle_from(body: dict):
    """從 body 取出字幕設定，回傳 (開關, 目標語言, 錯誤回應)。

    兩個都只在呼叫端明確帶了那個鍵時才回非 None——部分更新不可以把沒提到的設定
    清掉。

    開啟字幕翻譯一定要有目標語言，否則 Pydantic 那關會擋下整份設定。呼叫端這次
    沒帶目標語言時，讀目前存著的值來補；補不出來才拒絕。
    """
    enabled = bool(body["translate_subtitle"]) if "translate_subtitle" in body else None

    target = None
    if "subtitle_target_lang" in body:
        raw = body.get("subtitle_target_lang")
        target = str(raw).strip() if raw is not None else ""

    if enabled and not (target if target is not None else _stored_subtitle_target()):
        return (
            None,
            None,
            JSONResponse(
                status_code=400,
                content={
                    "ok": False,
                    "error": "subtitle_target_lang is required when "
                    "translate_subtitle is enabled.",
                },
            ),
        )
    return enabled, target, None


def _engine_settings_from(body: dict, engine: str) -> dict:
    """整理出兩個供應商的設定值。

    llm 引擎沒給端點與模型時，從玩家已經設好的 LLM 推導——這樣打開翻譯不需要
    任何額外設定就能用。
    """

    def text(key: str, default=None):
        value = body.get(key)
        return str(value).strip() if value else default

    llm_endpoint = text("llm_endpoint")
    llm_model = text("llm_model")
    if engine == "llm" and (not llm_endpoint or not llm_model):
        try:
            block = _get_openai_llm(_load_conf())
        except Exception as e:
            logger.warning(
                f"[translator] could not read player LLM: {type(e).__name__}"
            )
            block = None
        if block is not None:
            llm_endpoint = llm_endpoint or _derive_llm_endpoint(block.get("base_url"))
            model = block.get("model")
            llm_model = llm_model or (str(model) if model is not None else None)

    return {
        "deeplx_endpoint": text("deeplx_endpoint"),
        "deeplx_target_lang": text("deeplx_target_lang", DEFAULT_DEEPLX_TARGET),
        "llm_target_lang": text("llm_target_lang", DEFAULT_LLM_TARGET),
        "llm_api_endpoint": llm_endpoint,
        "llm_model": llm_model,
    }


def _write_translator_config(
    *,
    enabled: bool,
    engine: str,
    speak_voice: Optional[str],
    deeplx_endpoint: Optional[str],
    deeplx_target_lang: Optional[str],
    llm_target_lang: Optional[str],
    llm_api_endpoint: Optional[str],
    llm_model: Optional[str],
    subtitle_enabled: Optional[bool] = None,
    subtitle_target_lang: Optional[str] = None,
) -> dict:
    """就地改寫翻譯設定，回傳「實際寫了哪些」。

    絕不刪除或清空 llm／deeplx／tencent 子區塊——驗證器要求啟用中供應商的區塊
    必須存在，砍掉等於埋一顆下次開機才爆的雷。這裡只在既有區塊裡改值。

    兩個必填的葉節點（translate_audio、translate_provider）找不到就丟 KeyError：
    它們是這個功能的骨架，缺了代表 conf.yaml 結構壞了，該吵不該默默跳過。
    其餘的都是「有給才寫」，字幕那兩個還允許不存在時補上——早期的 conf.yaml
    沒有它們，不該讓整個存檔失敗。
    """
    _validate_translator_path()
    lines = _read_conf_lines()

    tc_start, tc_end = block_extent(lines, "translator_config")
    written: dict = {}

    # 骨架：缺了就吵。
    if not _rewrite_bool_leaf(lines, tc_start, tc_end, "translate_audio", enabled):
        raise KeyError("translate_audio leaf not found in translator_config")
    written["translate_audio"] = enabled

    if not _rewrite_leaf(lines, tc_start, tc_end, "translate_provider", engine):
        raise KeyError("translate_provider leaf not found in translator_config")
    written["translate_provider"] = engine

    # 字幕：純顯示用，跟 translate_audio 無關。早期的 conf.yaml 沒有這兩行，
    # 補上而不是失敗。插入會讓行數增加，區塊尾端要跟著往後移，否則底下找
    # llm／deeplx 時的範圍判斷會錯位。
    if subtitle_enabled is not None:
        tc_end = upsert_leaf(
            lines, tc_start, tc_end, "translate_subtitle", str(bool(subtitle_enabled))
        )
        written["translate_subtitle"] = subtitle_enabled
    if subtitle_target_lang is not None:
        tc_end = upsert_leaf(
            lines,
            tc_start,
            tc_end,
            "subtitle_target_lang",
            _quote_yaml_scalar(subtitle_target_lang),
        )
        written["subtitle_target_lang"] = subtitle_target_lang

    # 各供應商的巢狀葉節點：有給值才寫。
    nested = {
        "llm": [
            ("target_lang", llm_target_lang),
            ("api_endpoint", llm_api_endpoint),
            ("model", llm_model),
        ],
        "deeplx": [
            ("deeplx_target_lang", deeplx_target_lang),
            ("deeplx_api_endpoint", deeplx_endpoint),
        ],
    }
    for block, leaves in nested.items():
        if not any(value for _, value in leaves):
            continue
        try:
            b_start, b_end = block_extent(lines, block, start_from=tc_start)
        except KeyError:
            logger.warning(f"[translator] {block} block not found; left unchanged")
            continue
        # 區塊必須仍在 translator_config 之內——同名的鍵在檔案別處也可能有。
        if b_start > tc_end:
            continue
        for key, value in leaves:
            if value and _rewrite_leaf(lines, b_start, b_end, key, value):
                written[f"{block}.{key}"] = value

    # edge_tts 的嗓音是另一個頂層區塊，順手一起設。
    if speak_voice:
        try:
            e_start, e_end = block_extent(lines, "edge_tts")
        except KeyError:
            logger.warning("[translator] edge_tts block not found; voice not changed")
        else:
            if _rewrite_leaf(lines, e_start, e_end, "voice", speak_voice):
                written["edge_tts.voice"] = speak_voice
            else:
                logger.warning("[translator] edge_tts.voice leaf not found")

    _write_conf(lines)
    return written


# --------------------------------------------------------------------------- #
# Route factory
# --------------------------------------------------------------------------- #


def init_translator_route() -> APIRouter:
    """跨語言語音與字幕翻譯的端點。

    - GET  /api/translator-config -> current translator_config + base voice
    - POST /api/translator-config -> enable/disable + provider + target lang + voice
    """
    router = APIRouter()

    @router.get("/api/translator-config")
    async def get_translator_config(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            data = _load_conf()
        except Exception as e:
            logger.error(f"[translator] read failed: {type(e).__name__}")
            return JSONResponse(
                status_code=500, content={"error": "could not read config"}
            )

        block = _get_translator_block(data)
        if block is None:
            return JSONResponse(
                status_code=500,
                content={"error": "translator_config block missing in conf.yaml"},
            )

        provider = str(block.get("translate_provider") or "llm")
        subtitle_target = block.get("subtitle_target_lang")
        return JSONResponse(
            {
                "enabled": bool(block.get("translate_audio")),
                # UI 只提供 llm／deeplx 兩個選項。conf 設成 tencent 時選單顯示
                # llm，但 raw_provider 誠實地說出真正設定的是什麼——不要讓畫面
                # 假裝一個它其實沒在用的值。
                "engine": provider if provider in VALID_ENGINES else "llm",
                "raw_provider": provider,
                "llm_target_lang": _nested(
                    block, "llm", "target_lang", DEFAULT_LLM_TARGET
                ),
                "llm_endpoint": _nested(block, "llm", "api_endpoint"),
                "llm_model": _nested(block, "llm", "model"),
                "deeplx_target_lang": _nested(
                    block, "deeplx", "deeplx_target_lang", DEFAULT_DEEPLX_TARGET
                ),
                "deeplx_endpoint": _nested(
                    block, "deeplx", "deeplx_api_endpoint", DEFAULT_DEEPLX_ENDPOINT
                ),
                "speak_voice": _get_edge_tts_voice(data) or "",
                "default_jp_voice": DEFAULT_JP_VOICE,
                "translate_subtitle": bool(block.get("translate_subtitle")),
                "subtitle_target_lang": (
                    str(subtitle_target) if subtitle_target is not None else ""
                ),
            }
        )

    @router.post("/api/translator-config")
    async def save_translator_config(request: Request):
        if not _is_local_request(request):
            return _forbidden()

        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                status_code=400, content={"ok": False, "error": "Invalid JSON body."}
            )

        engine = str(body.get("engine", "llm")).strip().lower()
        if engine not in VALID_ENGINES:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "engine must be 'llm' or 'deeplx'."},
            )

        subtitle_enabled, subtitle_target_lang, bad = _subtitle_from(body)
        if bad:
            return bad

        try:
            written = await asyncio.to_thread(
                _write_translator_config,
                # 語音翻譯現在是自動判斷的（逐句比對聲音語言與回覆語言），沒有
                # 使用者開關。body 沒帶就當開著，引擎才會被建起來；呼叫端明確
                # 送 False 仍然照做，留給手動覆寫。
                enabled=bool(body.get("enabled", True)),
                engine=engine,
                # 嗓音不從這裡設。說話的聲音是在角色管理裡選一次的，翻譯只管
                # 翻成什麼語言。傳 None 讓寫入器完全不碰 edge_tts.voice。
                speak_voice=None,
                subtitle_enabled=subtitle_enabled,
                subtitle_target_lang=subtitle_target_lang,
                **_engine_settings_from(body, engine),
            )
        except Exception as e:
            logger.error(f"[translator] write failed: {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not write config file."},
            )

        logger.info(
            f"[translator] saved (engine={engine}, subtitle={subtitle_enabled})"
        )
        return JSONResponse(
            {
                "ok": True,
                "enabled": written["translate_audio"],
                "engine": engine,
                "translate_subtitle": (
                    subtitle_enabled
                    if subtitle_enabled is not None
                    else bool(written.get("translate_subtitle"))
                ),
                "subtitle_target_lang": subtitle_target_lang or "",
                # 回應形狀的相容欄位，UI 已經不讀它了。
                "speak_voice": "",
                "written": written,
                "restart_required": True,
            }
        )

    @router.post("/api/translator-config/test")
    async def test_translator(request: Request):
        """Run one real translation through the saved config and report what happened.

        Every way this feature fails is silent. A reasoning model puts the answer
        in reasoning_content and leaves content empty; a slow one exceeds the
        timeout; a wrong endpoint or model 404s. In all of those cases
        LLMTranslate falls back to returning the input verbatim, so the character
        simply speaks untranslated text with no error anywhere the user can see —
        which is indistinguishable from "translation is off". This endpoint makes
        the outcome visible: it reports the returned text and, crucially, whether
        the translator actually changed anything.
        """
        if not _is_local_request(request):
            return _forbidden()

        sample = TRANSLATOR_TEST_SAMPLE
        try:
            from .config_manager.utils import read_yaml, validate_config
            from .translate.translate_factory import TranslateFactory

            config = validate_config(read_yaml(CONF_PATH))
            translator = (
                config.character_config.tts_preprocessor_config.translator_config
            )
            if not translator.translate_audio:
                return JSONResponse(
                    {"ok": False, "reason": "disabled", "error": "translator is off"}
                )
            engine = TranslateFactory.get_translator(
                translator.translate_provider,
                getattr(translator, translator.translate_provider).model_dump(),
            )
        except Exception as e:
            logger.error(f"translator test could not build engine: {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "reason": "config", "error": str(e)},
            )

        started = time.monotonic()
        try:
            # translate() is blocking (httpx.post) — same reason conversation_utils
            # wraps it in to_thread. Never block the event loop from a route.
            result = await asyncio.to_thread(engine.translate, sample)
        except Exception as e:
            logger.error(f"translator test raised: {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "reason": "error", "error": str(e)},
            )
        elapsed = round(time.monotonic() - started, 1)

        ok, reason = classify_translation_test(sample, result)
        return JSONResponse(
            {
                "ok": ok,
                "reason": reason,
                "sample": sample,
                "result": str(result),
                "seconds": elapsed,
                "provider": translator.translate_provider,
            }
        )

    return router
