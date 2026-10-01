"""引擎與硬體相關的設定：讓同一份程式在弱機與強機上都跑得起來。

名字叫 perf，但它真正的主業是**引擎切換**——語音辨識用哪一個、語音合成用哪一個、
以及那些引擎自己的設定。效能預設（一鍵套用一組數值）只是其中一個端點。

這個模組管的東西，以及跟鄰居的分界：

- **語音辨識引擎**（asr_config.asr_model）與雲端引擎的憑證。注意設定頁那個「ASR」
  分頁管的是瀏覽器端的麥克風與 VAD，跟後端用哪個引擎無關——引擎的選擇在這裡。
- **語音合成引擎**（tts_config.tts_model）與 GPT-SoVITS 的參考音訊設定。
  text_split_method／batch_size 這些維持範本預設，不是使用者該面對的選擇。
- **效能預設**：一次套用一組引擎背景工作的頻率與放在心上的數量。只碰這些數字，
  不碰語音辨識與聲音。

兩件跟正確性有關的事：

1. **每次巢狀寫入都限定在該子區塊的範圍內**。好幾個引擎區塊共用同樣的葉節點名字
   （api_key、model），平掃著改會寫到別的引擎去，而且不會有任何徵兆。
2. **雲端金鑰讀出來一律遮罩，永遠不進 log。**

restart_required 對這裡的每一個改動都是誠實的 True：引擎設定在 server 啟動時就被
烤進 CharacterConfig，改完要重啟或重選角色才會生效。
"""

import asyncio
import os
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
    sub_block_extent as _sub_block_extent,
    read_conf_lines as _read_conf_lines,
    rewrite_str_leaf as _rewrite_leaf,
    write_conf as _write_conf,
)

from .config_manager.utils import read_yaml


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

# 效能預設：引擎背景工作每幾輪跑一次，以及她同時放在心上的目標／想法數量。
#
# 只寫這幾個數字。語音辨識、聲音不歸效能預設管：以前三個預設都寫死 edge-tts，
# 選一次「高效能」就把訓練好的聲音打回內建語音。標準＝出廠預設
# （engine_config_route.EVERY_DEFAULTS）。
PRESETS: dict[str, dict[str, Any]] = {
    # 輕量：弱機 / 共用機。每一項背景工作都是多一次模型呼叫。
    "light": {
        "emotion_every": 2,
        "memory_every": 3,
        "self_memory_every": 3,
        "goal_every": 8,
        "reflection_every": 12,
        "goals_shown": 2,
        "thoughts_shown": 1,
    },
    "standard": {
        "emotion_every": 1,
        "memory_every": 2,
        "self_memory_every": 2,
        "goal_every": 4,
        "reflection_every": 6,
        "goals_shown": 3,
        "thoughts_shown": 2,
    },
    # 高效能：強機，或背景工作另外交給一台電腦的模型。
    "high": {
        "emotion_every": 1,
        "memory_every": 1,
        "self_memory_every": 1,
        "goal_every": 3,
        "reflection_every": 4,
        "goals_shown": 4,
        "thoughts_shown": 3,
    },
}


def _current_preset() -> str:
    """目前的數字正好是哪一個預設；都對不上就是 custom。"""
    from .engine_config_route import EVERY_KEYS, read_engine_settings

    now = read_engine_settings()
    for name, bundle in PRESETS.items():
        if all(int(now[key]) == int(bundle[key]) for key in EVERY_KEYS):
            return name
    return "custom"


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


def _reference_voices() -> list:
    """列出可以直接選用的參考音。

    GPT-SoVITS 是 zero-shot 克隆：聲線完全由參考音決定，所以「換聲音」等於
    「換這個檔案」。原本 UI 只能手打絕對路徑——打錯了不會有任何錯誤訊息，
    只是合成時靜默失敗。

    掃描的目錄是 conf.yaml 裡那個全域 ref_audio_path 的所在資料夾：使用者本來
    就把參考音放在一起，不必再多一個設定項。

    每個 wav 可以有一個同名的 .txt 當逐字稿（sidecar）。有的話一併回傳，前端
    選了就自動把 prompt_text 填上——參考音跟它的逐字稿是一組的，分開填等於
    給使用者一個對不起來就會壞掉的機會。
    """
    conf = read_yaml(CONF_PATH) or {}
    node: Any = conf
    for key in ("character_config", "tts_config", "gpt_sovits_tts", "ref_audio_path"):
        node = node.get(key) if isinstance(node, dict) else None
    global_ref = str(node or "").strip()
    if not global_ref:
        return []
    folder = os.path.dirname(global_ref)
    if not folder or not os.path.isdir(folder):
        return []

    voices = []
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith((".wav", ".mp3", ".flac", ".m4a", ".ogg")):
            continue
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        transcript = ""
        sidecar = os.path.splitext(path)[0] + ".txt"
        if os.path.isfile(sidecar):
            try:
                with open(sidecar, encoding="utf-8") as f:
                    transcript = f.read().strip()
            except Exception as e:
                logger.warning(f"[perf] 讀不了逐字稿 {sidecar}：{type(e).__name__}")
        voices.append(
            {
                "path": path,
                "label": os.path.splitext(name)[0],
                "prompt_text": transcript,
            }
        )
    return voices


def init_perf_route() -> APIRouter:
    """引擎與硬體設定的端點。只接受可信來源。

    - GET  /api/perf                  -> ASR/TTS engine + creds(masked) + current preset
    - POST /api/perf/asr              -> set asr_model + cloud creds
    - POST /api/perf/tts              -> set tts_model + gpt_sovits fields
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
                "asr_models": sorted(ASR_MODELS),
                "tts_models": sorted(TTS_MODELS),
                "gpt_sovits_langs": sorted(GPT_SOVITS_LANGS),
                "reference_voices": _reference_voices(),
                "presets": sorted(PRESETS.keys()),
                "current_preset": _current_preset(),
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

    @router.post("/api/perf/preset")
    async def apply_preset(request: Request):
        """套用一組具名的預設（輕量／標準／高效能），一次寫入。

        一次讀、一次寫，不會出現改到一半的中間狀態。套用之後每個數字還是可以個別
        調整，對不上任何預設時 GET 會說 custom。
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
    """一次寫入把整組預設值全部套用：讀一次、改引擎那幾個數字、寫一次。"""

    with open(CONF_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # --- 引擎背景工作的頻率（接 character_engine_agent 時真正影響速度的是這幾個）---
    from .engine_config_route import EVERY_KEYS, apply_engine_settings

    apply_engine_settings(lines, {k: bundle[k] for k in EVERY_KEYS if k in bundle})

    _write_conf(lines)
    return True
