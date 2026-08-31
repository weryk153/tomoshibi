"""引擎與硬體相關的設定：讓同一份程式在弱機與強機上都跑得起來。

名字叫 perf，但它真正的主業是**引擎切換**——語音辨識用哪一個、語音合成用哪一個、
以及那些引擎自己的設定。效能預設（一鍵套用一組數值）只是其中一個端點。

這個模組管的東西，以及跟鄰居的分界：

- **語音辨識引擎**（asr_config.asr_model）與雲端引擎的憑證。注意設定頁那個「ASR」
  分頁管的是瀏覽器端的麥克風與 VAD，跟後端用哪個引擎無關——引擎的選擇在這裡。
- **語音合成引擎**（tts_config.tts_model）與 GPT-SoVITS 的參考音訊設定。
  text_split_method／batch_size 這些維持範本預設，不是使用者該面對的選擇。
- **ollama_llm.keep_alive**：本地模型在記憶體裡待多久。
- **記憶整理頻率**：memory_route 也有同一個設定的寫入端點，這裡再開一個是為了讓
  「效能」分頁能一次調完，以及讓預設包能整批套用。

兩件跟正確性有關的事：

1. **每次巢狀寫入都限定在該子區塊的範圍內**。好幾個引擎區塊共用同樣的葉節點名字
   （api_key、model），平掃著改會寫到別的引擎去，而且不會有任何徵兆。
2. **雲端金鑰讀出來一律遮罩，永遠不進 log。**

restart_required 對這裡的每一個改動都是誠實的 True：引擎設定在 server 啟動時就被
烤進 CharacterConfig，改完要重啟或重選角色才會生效。
"""

import asyncio
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from loguru import logger

from .api_guard import (
    is_trusted_request as _is_local_request,
    forbidden as _forbidden,
    mask_key as _mask_key,
)

from .conf_editor import (
    CONF_PATH,
    block_extent,
    character_config_extent,
    nested_extent,
    sub_block_extent as _sub_block_extent,
    read_conf_lines as _read_conf_lines,
    rewrite_int_leaf as _rewrite_int_leaf,
    rewrite_str_leaf as _rewrite_leaf,
    write_conf as _write_conf,
)

from .config_manager.utils import read_yaml
from . import memory_core


# --------------------------------------------------------------------------- #
# 界限與允許清單只在這裡定義一次，端點與前端都從這裡拿。
# --------------------------------------------------------------------------- #

# ASR engines the UI accepts. faster_whisper needs an extra `pip install
# faster-whisper` (+ ctranslate2 / model download) that isn't bundled. We still
# ACCEPT it here (rather than 400-ing the existing UI, whose preset/dropdown still
# offer it) because it is now SAFE at runtime: service_context.init_asr falls back
# to the bundled sherpa_onnx_asr if the chosen engine can't load, so picking
# faster_whisper without it installed quietly uses sherpa instead of bricking.
ASR_MODELS = {"sherpa_onnx_asr", "faster_whisper", "groq_whisper_asr", "azure_asr"}
# UI 提供的語音合成引擎。
TTS_MODELS = {"edge_tts", "gpt_sovits_tts"}

# gpt_sovits_tts.text_lang / prompt_lang allow-list offered by the UI's language
# selects. GPT-SoVITS itself just forwards whatever string tts/gpt_sovits_tts.py
# hands it (no client-side validation — see that file's `data` payload), so this
# is not "what the server accepts" but a deliberately small, well-supported
# subset: the same zh/en/ja/ko/yue family the bundled sherpa_onnx_asr sense_voice
# model already covers (config_templates/conf.default.yaml's sherpa_onnx_asr
# comment), plus 'auto' for GPT-SoVITS's own language auto-detection.
GPT_SOVITS_LANGS = {"zh", "en", "ja", "ko", "yue", "auto"}

# keep_alive: -1 = pin in RAM forever; 0 = unload immediately; otherwise seconds.
KEEP_ALIVE_MIN = -1
KEEP_ALIVE_MAX = 86400  # 24h hard ceiling


# 效能預設：一組挑好的數值，走的是底下那些既有的寫入器，不是另一條捷徑。
#
# 預設只是**起點**。套用之後每個控制項照樣可以個別調整，而且不點就完全不會動——
# conf.yaml 出廠的值不受影響。
PRESETS: dict[str, dict[str, Any]] = {
    # 輕量：弱機 / 共用機。最省。
    "light": {
        "asr_model": "sherpa_onnx_asr",
        "tts_model": "edge_tts",
        "core_memory_max_chars": 1000,
        "memory_consolidation_interval": 3,
        "keep_alive": 300,
    },
    # 標準：預設值（基本等於出廠的輕量預設）。
    "standard": {
        "asr_model": "sherpa_onnx_asr",
        "tts_model": "edge_tts",
        "core_memory_max_chars": 1500,
        "memory_consolidation_interval": 1,
        "keep_alive": 1800,
    },
    # 高效能：強機。ASR 維持內建的 sherpa_onnx_asr（離線、零額外相依）——不換成
    # faster_whisper，因為它的相依沒打包進來、換了一重開就起不來。「高效能」差別在
    # 記憶體 / keep_alive 這些旋鈕。TTS 也不自動換 gpt_sovits（需外部服務 + 參考音檔）。
    "high": {
        "asr_model": "sherpa_onnx_asr",
        "tts_model": "edge_tts",
        "core_memory_max_chars": 3000,
        "memory_consolidation_interval": 1,
        "keep_alive": 3600,
    },
}


# --- 讀設定 ----------------------------------------------------------------- #


def _load_plain() -> Any:
    return read_yaml(CONF_PATH) or {}


def _asr_from_conf() -> dict:
    """讀語音辨識的引擎與雲端憑證（憑證一律遮罩）。"""
    out = {
        "asr_model": "sherpa_onnx_asr",
        "groq_api_key_masked": "",
        "azure_api_key_masked": "",
        "azure_region": "",
    }
    try:
        data = _load_plain()
        asr = (data.get("character_config", {}) or {}).get("asr_config", {}) or {}
        m = asr.get("asr_model")
        if m is not None:
            out["asr_model"] = str(m)
        groq = asr.get("groq_whisper_asr", {}) or {}
        out["groq_api_key_masked"] = _mask_key(groq.get("api_key"))
        azure = asr.get("azure_asr", {}) or {}
        out["azure_api_key_masked"] = _mask_key(azure.get("api_key"))
        if azure.get("region") is not None:
            out["azure_region"] = str(azure.get("region"))
    except Exception:
        pass
    return out


def _tts_from_conf() -> dict:
    """讀語音合成的引擎與 GPT-SoVITS 的參考音訊設定。"""
    out = {
        "tts_model": "edge_tts",
        "gpt_sovits_api_url": "",
        "gpt_sovits_ref_audio_path": "",
        "gpt_sovits_prompt_text": "",
        "gpt_sovits_text_lang": "zh",
        "gpt_sovits_prompt_lang": "zh",
    }
    try:
        data = _load_plain()
        tts = (data.get("character_config", {}) or {}).get("tts_config", {}) or {}
        m = tts.get("tts_model")
        if m is not None:
            out["tts_model"] = str(m)
        gs = tts.get("gpt_sovits_tts", {}) or {}
        if gs.get("api_url") is not None:
            out["gpt_sovits_api_url"] = str(gs.get("api_url"))
        if gs.get("ref_audio_path") is not None:
            out["gpt_sovits_ref_audio_path"] = str(gs.get("ref_audio_path"))
        if gs.get("prompt_text") is not None:
            out["gpt_sovits_prompt_text"] = str(gs.get("prompt_text"))
        if gs.get("text_lang") is not None:
            out["gpt_sovits_text_lang"] = str(gs.get("text_lang"))
        if gs.get("prompt_lang") is not None:
            out["gpt_sovits_prompt_lang"] = str(gs.get("prompt_lang"))
    except Exception:
        pass
    return out


def _engine_overrides_by_character() -> dict:
    """哪些角色檔自己釘了引擎。

    角色一被載入，它自己的 asr_config／tts_config 就整個取代 conf.yaml 的——
    init_tts／init_asr 讀的是角色那一份，不是全域那一份。

    所以在這一頁選的引擎，下次切換角色時可能無聲無息被換回去，而畫面上沒有任何
    線索。回報這些覆寫，UI 才能事先講清楚哪些設定其實不會生效——否則使用者會花
    一個晚上想不通為什麼聲音一直沒變。

    用 conf_name 當鍵：那是前端已經握有的東西（來自 set-model-and-conf）。
    """
    overrides: dict[str, dict[str, str]] = {}
    characters_dir = Path("characters")
    if not characters_dir.is_dir():
        return overrides
    for entry in sorted(characters_dir.glob("*.yaml")):
        try:
            data = read_yaml(str(entry)) or {}
        except Exception:
            continue
        character = data.get("character_config", {}) or {}
        name = str(character.get("conf_name") or entry.stem)
        pinned = {}
        tts_model = (character.get("tts_config", {}) or {}).get("tts_model")
        if tts_model:
            pinned["tts_model"] = str(tts_model)
        asr_model = (character.get("asr_config", {}) or {}).get("asr_model")
        if asr_model:
            pinned["asr_model"] = str(asr_model)
        if pinned:
            overrides[name] = pinned
    return overrides


def _keep_alive_from_conf() -> int:
    """讀本機模型在記憶體裡留多久（秒；-1 代表一直留著）。"""
    try:
        data = _load_plain()
        ka = (
            data.get("character_config", {})
            .get("agent_config", {})
            .get("llm_configs", {})
            .get("ollama_llm", {})
            .get("keep_alive")
        )
        if ka is None:
            return 1800
        return int(ka)
    except Exception:
        return 1800


def _interval_from_conf() -> int:
    """讀記憶整理的頻率（每 N 輪一次，夾在允許的集合內）。"""
    try:
        data = _load_plain()
        v = (data.get("character_config", {}) or {}).get(
            "memory_consolidation_interval"
        )
        if v is None:
            return memory_core.CONSOLIDATE_INTERVAL_DEFAULT
        return memory_core._clamp_interval(v)
    except Exception:
        return memory_core.CONSOLIDATE_INTERVAL_DEFAULT


# --- 寫設定 ----------------------------------------------------------------- #
#
# 每一次寫入都限定在該子區塊的範圍內，絕不平掃整個檔案——好幾個引擎共用同樣的
# 葉節點名字（api_key、model），平掃會寫到別的引擎去，而且不會有任何徵兆。


def _asr_config_extent(lines: list) -> tuple[int, int]:
    return block_extent(lines, "asr_config")


def _tts_config_extent(lines: list) -> tuple[int, int]:
    return block_extent(lines, "tts_config")


def _write_engine_settings(
    parent_key: str,
    model_key: str,
    model: Optional[str],
    sub_blocks: dict,
) -> bool:
    """改寫一個引擎區塊：主選擇 + 各子區塊裡的欄位。

    ASR 與 TTS 是同一個形狀——「用哪個引擎」加上「那個引擎自己的設定」，差別只在
    區塊名稱與欄位清單。

    ``sub_blocks`` 形如 ``{"gpt_sovits_tts": {"api_url": "...", "prompt_text": None}}``。
    值為 None 的欄位跳過，這樣只改一個欄位時不會碰到旁邊的欄位與註解。整個子區塊
    的欄位都是 None 時連找都不找——找不到就丟 KeyError，不該為了沒人要寫的東西而
    失敗。

    葉節點必須已經存在。找不到就丟：這些是引擎的必要欄位，缺了代表設定檔結構壞了。
    """
    lines = _read_conf_lines()
    parent_start, parent_end = block_extent(lines, parent_key)

    if model is not None and not _rewrite_leaf(
        lines, parent_start, parent_end, model_key, model
    ):
        raise KeyError(f"{model_key} leaf not found in {parent_key}")

    for block_name, fields in sub_blocks.items():
        wanted = {k: v for k, v in fields.items() if v is not None}
        if not wanted:
            continue
        start, end = _sub_block_extent(lines, parent_start, parent_end, block_name)
        if start is None:
            raise KeyError(f"{block_name} sub-block not found in {parent_key}")
        for key, value in wanted.items():
            if not _rewrite_leaf(lines, start, end, key, value):
                raise KeyError(f"{key} leaf not found in {block_name}")

    _write_conf(lines)
    return True


def _write_asr(
    asr_model: Optional[str],
    groq_api_key: Optional[str],
    azure_api_key: Optional[str],
    azure_region: Optional[str],
) -> bool:
    """改寫語音辨識引擎的選擇，以及雲端引擎的憑證。"""
    return _write_engine_settings(
        "asr_config",
        "asr_model",
        asr_model,
        {
            "groq_whisper_asr": {"api_key": groq_api_key},
            "azure_asr": {"api_key": azure_api_key, "region": azure_region},
        },
    )


def _write_tts(
    tts_model: Optional[str],
    gpt_sovits_api_url: Optional[str],
    gpt_sovits_ref_audio_path: Optional[str],
    gpt_sovits_prompt_text: Optional[str] = None,
    gpt_sovits_text_lang: Optional[str] = None,
    gpt_sovits_prompt_lang: Optional[str] = None,
) -> bool:
    """改寫語音合成引擎的選擇，以及 GPT-SoVITS 的參考音訊設定。"""
    return _write_engine_settings(
        "tts_config",
        "tts_model",
        tts_model,
        {
            "gpt_sovits_tts": {
                "api_url": gpt_sovits_api_url,
                "ref_audio_path": gpt_sovits_ref_audio_path,
                "prompt_text": gpt_sovits_prompt_text,
                "text_lang": gpt_sovits_text_lang,
                "prompt_lang": gpt_sovits_prompt_lang,
            }
        },
    )


def _write_keep_alive(keep_alive: int) -> bool:
    """改寫 ollama_llm.keep_alive（模型在記憶體裡留多久，秒；-1 代表永遠）。

    路徑是 agent_config → llm_configs → ollama_llm。逐層鑽是必要的：keep_alive
    這種名字在別的供應商區塊底下也可能出現。
    """
    lines = _read_conf_lines()
    start, end = nested_extent(lines, "agent_config", "llm_configs", "ollama_llm")
    if not _rewrite_int_leaf(lines, start, end, "keep_alive", keep_alive):
        raise KeyError("keep_alive leaf not found in ollama_llm")
    _write_conf(lines)
    return True


def _write_consolidation_interval(interval: int) -> bool:
    """改寫記憶整理的頻率（每 N 輪一次）。"""
    lines = _read_conf_lines()
    start, end = character_config_extent(lines)
    if not _rewrite_int_leaf(
        lines, start, end, "memory_consolidation_interval", interval
    ):
        raise KeyError(
            "memory_consolidation_interval leaf not found in character_config"
        )
    _write_conf(lines)
    return True


# --------------------------------------------------------------------------- #
# 端點共用
# --------------------------------------------------------------------------- #


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "error": message})


async def _parse_body(request: Request):
    """讀出 JSON body 並確認它是物件。回傳 (body, 錯誤回應)。"""
    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        return None, _error(400, "Invalid JSON body.")
    return body, None


def _choice(body: dict, key: str, allowed: set):
    """取出一個限定選項的字串欄位。沒帶回 (None, None)，帶了但不合法回錯誤。

    明確送 null 視同沒帶。重寫前這件事在不同欄位上不一致——語言欄位送 null 會被
    略過，引擎欄位送 null 會被當成空字串然後報「不是合法選項」。同一份 API 裡
    同樣的輸入該有同樣的意思。
    """
    if body.get(key) is None:
        return None, None
    value = str(body[key]).strip()
    if value not in allowed:
        return None, _error(400, f"{key} must be one of {sorted(allowed)}.")
    return value, None


def _secret(body: dict, key: str):
    """取出憑證欄位。

    只有帶了非空值才回傳——讀取時金鑰是遮罩過的，讓遮罩值原樣送回來會把真的
    金鑰覆蓋成一串星號。空值等於「沒有要改」。
    """
    value = body.get(key)
    return str(value) if value else None


def _text(body: dict, key: str):
    """取出一個可以被清空的文字欄位（帶了就算數，包括空字串）。"""
    if key not in body or body.get(key) is None:
        return None
    return str(body[key]).strip()


def _bounded_int(body: dict, key: str, low: int, high: int):
    """取出一個必填的整數欄位並檢查範圍。回傳 (值, 錯誤回應)。"""
    if key not in body:
        return None, _error(400, f"Missing '{key}' integer.")
    try:
        value = int(body[key])
    except (TypeError, ValueError):
        return None, _error(400, f"'{key}' must be an integer.")
    if value < low or value > high:
        return None, _error(400, f"'{key}' must be between {low} and {high}.")
    return value, None


async def _write_or_error(fn, *args, what: str):
    try:
        await asyncio.to_thread(fn, *args)
        return None
    except Exception as e:
        logger.error(f"[perf] {what} failed: {type(e).__name__}: {e}")
        return _error(500, "Could not write config file.")


# --- 端點 ------------------------------------------------------------------- #


def init_perf_route() -> APIRouter:
    """引擎與硬體設定的端點。只接受可信來源。

    - GET  /api/perf                  -> ASR/TTS engine + creds(masked) + keep_alive + interval
    - POST /api/perf/asr              -> set asr_model + cloud creds
    - POST /api/perf/tts              -> set tts_model + gpt_sovits fields
    - POST /api/perf/keep-alive       -> set ollama keep_alive
    - POST /api/perf/consolidation    -> set memory_consolidation_interval
    - POST /api/perf/preset           -> apply a named preset bundle (atomic, one write)
    """
    router = APIRouter()

    @router.get("/api/perf")
    async def get_perf(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        asr = _asr_from_conf()
        tts = _tts_from_conf()
        return JSONResponse(
            {
                **asr,
                **tts,
                "keep_alive": _keep_alive_from_conf(),
                "keep_alive_min": KEEP_ALIVE_MIN,
                "keep_alive_max": KEEP_ALIVE_MAX,
                "consolidation_interval": _interval_from_conf(),
                "consolidation_interval_choices": list(
                    memory_core.CONSOLIDATE_INTERVAL_CHOICES
                ),
                "asr_models": sorted(ASR_MODELS),
                "tts_models": sorted(TTS_MODELS),
                "gpt_sovits_langs": sorted(GPT_SOVITS_LANGS),
                "presets": sorted(PRESETS.keys()),
                "engine_overrides_by_character": _engine_overrides_by_character(),
            }
        )

    @router.post("/api/perf/asr")
    async def set_asr(request: Request):
        """設定語音辨識引擎，以及雲端引擎的憑證。"""
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        asr_model, bad = _choice(body, "asr_model", ASR_MODELS)
        if bad:
            return bad

        groq_api_key = _secret(body, "groq_api_key")
        azure_api_key = _secret(body, "azure_api_key")
        azure_region = _text(body, "azure_region")

        if all(
            v is None for v in (asr_model, groq_api_key, azure_api_key, azure_region)
        ):
            return _error(400, "Nothing to update.")

        bad = await _write_or_error(
            _write_asr,
            asr_model,
            groq_api_key,
            azure_api_key,
            azure_region,
            what="asr write",
        )
        if bad:
            return bad

        logger.info(f"[perf] asr saved (model={asr_model})")
        return JSONResponse(
            {
                "ok": True,
                "asr_model": asr_model or _asr_from_conf().get("asr_model"),
                "restart_required": True,
            }
        )

    @router.post("/api/perf/tts")
    async def set_tts(request: Request):
        """設定語音合成引擎，以及 GPT-SoVITS 的參考音訊。"""
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        tts_model, bad = _choice(body, "tts_model", TTS_MODELS)
        if bad:
            return bad
        text_lang, bad = _choice(body, "gpt_sovits_text_lang", GPT_SOVITS_LANGS)
        if bad:
            return bad
        prompt_lang, bad = _choice(body, "gpt_sovits_prompt_lang", GPT_SOVITS_LANGS)
        if bad:
            return bad

        api_url = _text(body, "gpt_sovits_api_url")
        ref_audio = _text(body, "gpt_sovits_ref_audio_path")
        # 參考音訊的逐字稿。它是選填的（沒有的話 GPT-SoVITS 品質變差但還是能跑），
        # 所以空字串是「使用者刻意清空」這個合法值，不是「沒帶這個欄位」。也不做
        # strip：逐字稿自己的前後空白不是我們該正規化的東西。
        prompt_text = (
            str(body["gpt_sovits_prompt_text"])
            if body.get("gpt_sovits_prompt_text") is not None
            else None
        )

        fields = (tts_model, api_url, ref_audio, prompt_text, text_lang, prompt_lang)
        if all(v is None for v in fields):
            return _error(400, "Nothing to update.")

        bad = await _write_or_error(_write_tts, *fields, what="tts write")
        if bad:
            return bad

        logger.info(f"[perf] tts saved (model={tts_model})")
        return JSONResponse({"ok": True, **_tts_from_conf(), "restart_required": True})

    @router.post("/api/perf/keep-alive")
    async def set_keep_alive(request: Request):
        """本地模型在記憶體裡待多久（秒；-1 代表一直留著）。"""
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        keep_alive, bad = _bounded_int(
            body, "keep_alive", KEEP_ALIVE_MIN, KEEP_ALIVE_MAX
        )
        if bad:
            return bad

        bad = await _write_or_error(
            _write_keep_alive, keep_alive, what="keep_alive write"
        )
        if bad:
            return bad

        logger.info(f"[perf] keep_alive saved (keep_alive={keep_alive})")
        return JSONResponse(
            {"ok": True, "keep_alive": keep_alive, "restart_required": True}
        )

    @router.post("/api/perf/consolidation")
    async def set_consolidation(request: Request):
        """記憶整理的頻率（每 N 輪一次）。memory 分頁也有同一個設定。"""
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        if "interval" not in body:
            return _error(400, "Missing 'interval' integer.")
        try:
            interval = int(body["interval"])
        except (TypeError, ValueError):
            return _error(400, "'interval' must be an integer.")
        choices = list(memory_core.CONSOLIDATE_INTERVAL_CHOICES)
        if interval not in choices:
            return _error(400, f"'interval' must be one of {choices}.")

        bad = await _write_or_error(
            _write_consolidation_interval, interval, what="consolidation write"
        )
        if bad:
            return bad

        logger.info(f"[perf] consolidation saved (interval={interval})")
        return JSONResponse(
            {"ok": True, "consolidation_interval": interval, "restart_required": True}
        )

    @router.post("/api/perf/preset")
    async def apply_preset(request: Request):
        """套用一組具名的預設（輕量／標準／高效能），一次寫入。

        預設碰到的每個葉節點都已經存在，所以一次掃描全部改完——不會出現改到一半
        的中間狀態。套用之後每個控制項還是可以個別調整，預設只是起點。
        """
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        name, bad = _choice(body, "name", set(PRESETS))
        if bad:
            return bad
        if name is None:
            return _error(400, f"name must be one of {sorted(PRESETS)}.")

        bundle = PRESETS[name]
        bad = await _write_or_error(_apply_preset_bundle, bundle, what="preset apply")
        if bad:
            return bad

        logger.info(f"[perf] preset applied (name={name})")
        return JSONResponse(
            {
                "ok": True,
                "preset": name,
                "applied": bundle,
                "restart_required": True,
            }
        )

    return router


def _apply_preset_bundle(bundle: dict) -> bool:
    """一次寫入把整組預設值全部套用。

    Reads the file once, rewrites every targeted leaf in-place (scoped to the right
    block extent), then one atomic write — so there is no partial-apply window. All
    leaves pre-exist in conf.yaml (validated by the surgical writers, which raise
    KeyError if a leaf is missing -> the whole apply fails cleanly, nothing written).
    """
    from .conf_editor import character_config_extent as _character_config_extent

    with open(CONF_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # --- character_config direct-child leaves ---
    cc_start, cc_end = _character_config_extent(lines)
    if "core_memory_max_chars" in bundle:
        if not _rewrite_int_leaf(
            lines,
            cc_start,
            cc_end,
            "core_memory_max_chars",
            int(bundle["core_memory_max_chars"]),
        ):
            raise KeyError("core_memory_max_chars leaf not found")
    if "memory_consolidation_interval" in bundle:
        if not _rewrite_int_leaf(
            lines,
            cc_start,
            cc_end,
            "memory_consolidation_interval",
            int(bundle["memory_consolidation_interval"]),
        ):
            raise KeyError("memory_consolidation_interval leaf not found")

    # --- asr_model (re-find extent on the current lines; line count unchanged) ---
    if "asr_model" in bundle:
        asr_start, asr_end = _asr_config_extent(lines)
        if not _rewrite_leaf(
            lines, asr_start, asr_end, "asr_model", str(bundle["asr_model"])
        ):
            raise KeyError("asr_model leaf not found")

    # --- tts_model ---
    if "tts_model" in bundle:
        tts_start, tts_end = _tts_config_extent(lines)
        if not _rewrite_leaf(
            lines, tts_start, tts_end, "tts_model", str(bundle["tts_model"])
        ):
            raise KeyError("tts_model leaf not found")

    # --- ollama 的 keep_alive（鑽三層）---
    if "keep_alive" in bundle:
        start, end = nested_extent(lines, "agent_config", "llm_configs", "ollama_llm")
        if not _rewrite_int_leaf(
            lines, start, end, "keep_alive", int(bundle["keep_alive"])
        ):
            raise KeyError("keep_alive leaf not found")

    _write_conf(lines)
    return True
