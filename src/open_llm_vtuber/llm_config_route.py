"""首次啟動的 LLM 設定：讓使用者填自己的模型服務，不必碰設定檔。

一個區塊打天下：OpenAI、Claude、Gemini、Ollama、LM Studio 都講 OpenAI 相容的
API，所以精靈永遠寫 openai_compatible_llm，靠 base_url ＋ model ＋ llm_api_key
三個值區分。

存檔時**同時**把 llm_provider 指向那個區塊，這一步不能省：agent 只讀
llm_provider 指名的那個供應商。一台原本指著 lmstudio_llm 的機器，若只寫了值卻
沒切選擇器，會「驗證通過、存檔成功、完全沒有效果」，而且哪裡都不會報錯。

「設定好了沒」不是看有沒有填東西，是看**能不能真的用**：

- 雲端端點：金鑰不是佔位符就算數。
- 本機 Ollama：光是填了位址不夠——要探測到 daemon 真的活著，而且它真的有那個
  模型。填了一個沒下載的模型就等於沒設定好，精靈該繼續出現。
  （雲端模型例外：名字帶 :cloud 的由 Ollama Cloud 服務，不會出現在本機清單裡。）

金鑰永遠不進 log，讀回去一律遮罩。存檔不會熱套用（conf.yaml 開機讀一次），所以
回應帶 restart_required。
"""

import json
import asyncio
from dataclasses import asdict
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse, StreamingResponse
from loguru import logger


# --- 常數 ------------------------------------------------------------------- #

from .conf_editor import (
    nested_extent,
    read_conf_lines as _read_conf_lines,
    upsert_leaf,
    upsert_nested_block,
    write_conf as _write_conf,
    split_leaf as _split_leaf,
)
from .api_guard import (
    forbidden as _forbidden,
    is_trusted_request as _is_local_request,
    make_yaml as _make_yaml,
    mask_key as _mask_key,
)
from .model_probe import (
    describe_ollama_model,
    list_lmstudio_models,
    list_ollama_models,
    ollama_installed,
    probe_lmstudio,
    probe_ollama,
)
from .model_profiles import profile_for, recommended_model
from . import ollama_installer
from .system_probe import total_ram_bytes

CONF_PATH = "conf.yaml"

OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434/v1"
OLLAMA_PULL_URL = "http://localhost:11434/api/pull"

# 推薦給第一次使用者的模型：免費、跑在自己機器上、約 1.9 GB，一般筆電帶得動。
# 精靈可以直接幫他下載，不會技術的人不必開終端機。跟預設設定範本裡的一致。
RECOMMENDED_OLLAMA_MODEL = "qwen2.5:3b"

LMSTUDIO_DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"
# OLLAMA_DEFAULT_BASE_URL 已在上方定義，這裡沿用同一個，不重複宣告。

# 偵測到的 backend → 要寫進哪個 conf 區塊。
_BACKEND_TO_PROVIDER = {"lmstudio": "lmstudio_llm", "ollama": "ollama_llm"}

# 驗證用那一次呼叫的逾時（秒）。
TEST_CALL_TIMEOUT = 12.0
# 本機模型另算，而且寬鬆得多：它的第一次推論要把權重載進記憶體，遠比雲端的
# 往返久。用同一個 12 秒的話，使用者剛下載完模型、精靈馬上就跟他說「連不上」
# ——那是最讓人放棄的時機。
LOCAL_TEST_CALL_TIMEOUT = 90.0
OLLAMA_PROBE_TIMEOUT = 4.0

# 供應商 → 預設的端點位址。呼叫端沒指定時才用這些。
#
# Anthropic 與 Google 都另外提供了 OpenAI 相容的端點，所以四家可以走同一套
# 設定，不必為每一家寫一個轉接層。
PROVIDER_DEFAULT_BASE_URL = {
    "openai": "https://api.openai.com/v1",
    "claude": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "ollama": OLLAMA_DEFAULT_BASE_URL,
}

# 這些值代表「還沒設定」，不是真的金鑰——範本裡的佔位字串與 Ollama 的免填值。
PLACEHOLDER_KEYS = {
    "YOUR API KEY HERE",
    "Your Open AI API key",
    "Your Gemini API Key",
    "your api key here",
    "ollama",
    "",
}


# --- 讀設定 ----------------------------------------------------------------- #


def _load_conf() -> Any:
    yaml = _make_yaml()
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        return yaml.load(f)


def _get_openai_block(data: Any) -> Optional[Any]:
    """openai_compatible_llm 那個區塊；路徑缺任何一層就回 None。"""
    try:
        return data["character_config"]["agent_config"]["llm_configs"][
            "openai_compatible_llm"
        ]
    except (KeyError, TypeError):
        return None


def _get_llm_provider(data: Any) -> Optional[str]:
    """目前選中的是哪一個供應商；路徑缺任何一層就回 None。"""
    try:
        return data["character_config"]["agent_config"]["agent_settings"][
            "basic_memory_agent"
        ]["llm_provider"]
    except (KeyError, TypeError):
        return None


def _get_system_host(data: Any) -> Optional[str]:
    try:
        return str(data["system_config"]["host"])
    except (KeyError, TypeError):
        return None


# --- 探測本機的 Ollama ------------------------------------------------------ #
#
# 從伺服器端問，不是從瀏覽器問：瀏覽器打 localhost:11434 會撞上 CORS，頁面走
# HTTPS 時還會被 mixed-content 擋掉。


async def _probe_ollama_models() -> dict:
    """
    Hit the local Ollama /api/tags endpoint and return its model list.

    Returns ``{"available": True, "models": [...]}`` on success, or
    ``{"available": False}`` if Ollama is not reachable.
    """
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_PROBE_TIMEOUT) as client:
            resp = await client.get(OLLAMA_TAGS_URL)
            resp.raise_for_status()
            payload = resp.json()
        models = [
            m.get("name")
            for m in payload.get("models", [])
            if isinstance(m, dict) and m.get("name")
        ]
        return {"available": True, "models": models}
    except Exception as e:
        # 連不上、逾時、回傳看不懂——都當成「Ollama 現在用不了」。
        logger.debug(f"Ollama probe failed: {type(e).__name__}")
        return {"available": False, "models": []}


# --------------------------------------------------------------------------- #
# "is configured" heuristic
# --------------------------------------------------------------------------- #


def _has_real_key(block: Optional[Any]) -> bool:
    """
    True only if the block holds a real, usable API key -- i.e. not missing and
    not one of PLACEHOLDER_KEYS. Used by GET /api/llm-config so the wizard can
    tell "a real key is on file" apart from "api_key_masked is non-empty",
    which is also true for a masked PLACEHOLDER value (e.g. 'your api key
    here' -> 'your****'). The wizard only appears when the stored key is a
    placeholder or otherwise unusable, so inferring from the mask alone made
    hasExistingKey true on every first-run path -- exactly the case this
    exists to distinguish.
    """
    if block is None:
        return False
    api_key = block.get("llm_api_key")
    return not ((api_key is None) or (str(api_key) in PLACEHOLDER_KEYS))


async def _is_configured(block: Optional[Any]) -> bool:
    """
    Decide whether the LLM is genuinely usable out of the box.

    Not configured (show wizard) if the key is a placeholder, OR if it still
    points at the local Ollama default but Ollama is not actually running.
    """
    if block is None:
        return False

    api_key = block.get("llm_api_key")
    base_url = block.get("base_url")
    model = block.get("model")

    key_is_placeholder = (api_key is None) or (str(api_key) in PLACEHOLDER_KEYS)

    base_url_str = str(base_url) if base_url is not None else ""
    is_ollama = (
        base_url_str.rstrip("/").startswith(OLLAMA_DEFAULT_BASE_URL.rstrip("/"))
        or ":11434" in base_url_str
    )

    if not is_ollama:
        # 雲端端點只要金鑰不是佔位符就算設定好了。
        return not key_is_placeholder

    # 本機這條路要多驗一步：金鑰欄位填 'ollama' 不代表能用，得確認 daemon 真的
    # 活著、而且真的有那個模型。填了一個沒下載的模型等於沒設定好。
    probe = await _probe_ollama_models()
    if not probe.get("available"):
        return False
    if model is None:
        return False
    model_str = str(model)
    # 名字帶 :cloud 的由 Ollama Cloud 服務，不會出現在本機清單裡，所以比對不到。
    # 那種情況只要 daemon 連得上就算設定好。
    if model_str.endswith(":cloud") or model_str.endswith("-cloud"):
        return True
    return model_str in probe.get("models", [])


async def _is_configured_for_conf(data: Any) -> bool:
    """
    Whole-config wrapper around ``_is_configured(block)`` that first checks which
    provider ``llm_provider`` actually selects, so a machine that has deliberately
    chosen a non-openai_compatible_llm provider (e.g. 'lmstudio_llm') is not
    treated as unconfigured just because the untouched openai_compatible_llm
    block still holds placeholder values.

    KNOWN LIMITATION: when llm_provider points elsewhere, this does not inspect
    whether THAT block is itself actually usable — only _is_configured() has
    that per-provider shape logic, and only for openai_compatible_llm. A
    llm_provider naming a block that is missing entirely from llm_configs, or
    that has a bad key / unreachable endpoint, makes agent_factory.py raise at
    startup (see its "Configuration not found for LLM provider" / interrupt
    lookup paths) — i.e. the agent may fail to start entirely, and this
    function will still report "configured" and keep the wizard hidden.
    Auditing every provider's own "is this usable" shape is a bigger project.
    Until then, this false-positive direction (wizard stays hidden on a broken
    non-openai provider) is accepted as far less harmful than the alternative
    (wizard pops on every launch for a user whose LLM already works), which is
    the regression this function exists to prevent.
    """
    llm_provider = _get_llm_provider(data)
    if llm_provider and llm_provider != "openai_compatible_llm":
        return True
    block = _get_openai_block(data)
    return await _is_configured(block)


# --- 用一次便宜的呼叫確認設定能用 ------------------------------------------- #


def _test_call_sync(base_url: str, model: str, api_key: str) -> tuple[bool, str]:
    """
    Make ONE minimal OpenAI-compatible chat completion to validate the combo.

    Runs in a thread (blocking openai client). Returns ``(ok, error_message)``.
    The error message is sanitized and NEVER contains the api_key.
    """
    from openai import OpenAI

    # Local endpoints (Ollama etc.) get a generous cold-start budget; cloud uses the
    # short timeout so a wrong URL/key fails fast.
    _bu = (base_url or "").lower()
    is_local = any(h in _bu for h in ("127.0.0.1", "localhost", "::1", ":11434"))
    call_timeout = LOCAL_TEST_CALL_TIMEOUT if is_local else TEST_CALL_TIMEOUT

    try:
        client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=call_timeout,
            max_retries=0,
        )
        client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            # 給 32 個 token 而不是 1，一般的對話模型才會真的吐出內容。
            #
            # 這裡**只確認呼叫成功**，不看回覆內容是不是空的。空回覆判斷不出
            # 任何東西：免費的雲端模型偶爾就是對一個 ping 回空，而會思考的模型
            # 反而會正常回答。真正處理「內容空但思考欄位有東西」的地方在串流層
            # （openai_compatible_llm 會退回去讀 reasoning 欄位），在這裡多做一道
            # 檢查，只會把話少的正常模型誤判成壞掉。
            max_tokens=32,
        )
        return True, ""
    except Exception as e:
        # 錯誤訊息要給人看，但絕不能帶出金鑰。
        msg = _sanitize_error(e, api_key)
        return False, msg


def _sanitize_error(exc: Exception, api_key: str) -> str:
    """把例外轉成使用者看得懂的一句話，而且永遠不會夾帶金鑰。

    先無條件把金鑰從訊息裡抹掉再處理——有些函式庫會把整個請求（含標頭）塞進
    例外訊息，那是金鑰外洩到畫面上、log 裡、甚至使用者截圖裡的最短路徑。
    """
    text = str(exc)
    if api_key:
        text = text.replace(api_key, "<redacted>")
    # 常見的幾種失敗給明確的指路，其他的只回例外型別。
    lowered = text.lower()
    if "401" in text or "unauthor" in lowered or "invalid_api_key" in lowered:
        return "Authentication failed — the API key was rejected. Check the key."
    if (
        "404" in text
        or "not found" in lowered
        or ("model" in lowered and "exist" in lowered)
    ):
        return "The model was not found at this endpoint. Check the model name."
    if "connect" in lowered or "timeout" in lowered or "refused" in lowered:
        return "Could not reach the endpoint. Check the URL (and that the server is running)."
    if "rate" in lowered and "limit" in lowered:
        return "Rate limited by the provider. Try again in a moment."
    # 認不出來的：只回例外型別，不回完整內容——那裡面可能有任何東西。
    return f"Test call failed ({type(exc).__name__}). Check the URL, model, and key."


async def _validate_combo(base_url: str, model: str, api_key: str) -> tuple[bool, str]:
    return await asyncio.to_thread(_test_call_sync, base_url, model, api_key)


def _resolve_base_url_default(provider: str, base_url: Optional[str]) -> Optional[str]:
    """
    Apply the provider's default base_url only when the client omitted the
    field entirely (or sent JSON null) -- i.e. ``base_url is None``.

    ``body.get("base_url")`` cannot tell "field absent" apart from "field
    present but empty" once collapsed with a plain truthiness check: both
    ``None`` and ``''`` are falsy. apikey mode omits base_url on purpose (it
    wants the provider default); custom mode always sends the field, so an
    empty string there means the user left the URL box blank and must see
    "Missing base_url.", not have it silently swapped for OpenAI's endpoint.
    """
    if base_url is None:
        return PROVIDER_DEFAULT_BASE_URL.get(provider)
    return base_url


# --- 寫入設定檔 ------------------------------------------------------------- #


def _quote_yaml_scalar(value: str) -> str:
    """
    Single-quote a scalar for YAML, matching the file's existing style (the
    openai_compatible_llm values are single-quoted). Escapes embedded quotes.
    """
    return "'" + str(value).replace("'", "''") + "'"


def _validate_path_with_ruamel(provider: str) -> None:
    """
    Confirm the given provider's block exists at the expected path before we
    touch the file. Uses ruamel round-trip load (per spec) so a malformed/missing
    structure fails loudly instead of corrupting the config.

    provider 是必填參數，沒有預設值：兩個呼叫端（write_provider_config、
    write_provider_config_and_use_mcpp）都會傳它們真正要寫的那個區塊，不能
    偷懶沿用 openai_compatible_llm 當預設值——不然哪天多了個忘記傳這個參數的
    呼叫端，目標明明是 lmstudio_llm，卻只驗證了 openai_compatible_llm 存不
    存在，驗過了但目標區塊其實不在，會晚一步才在逐行編輯時才炸開，而且是
    悄悄驗過錯的區塊，不是直接報錯。
    """
    yaml = _make_yaml()
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        data = yaml.load(f)
    try:
        block = data["character_config"]["agent_config"]["llm_configs"][provider]
    except (KeyError, TypeError):
        block = None
    if block is None:
        raise KeyError(
            f"{provider} block not found in conf.yaml "
            f"(character_config.agent_config.llm_configs.{provider})"
        )


# 允許寫入的供應商區塊。白名單而不是自由字串：provider 會被拿去組 YAML 路徑，
# 而路徑是請求可控的。
WRITABLE_PROVIDERS = frozenset({"lmstudio_llm", "ollama_llm", "openai_compatible_llm"})


def _point_llm_provider_at(lines: list, provider: str) -> None:
    """把 llm_provider 選擇器指向指定區塊，保留縮排與行尾註解。

    沒有這一步，一台 llm_provider 指著別的區塊的機器會「驗證通過、存檔成功」，
    然後 agent 繼續讀舊的供應商——哪裡都不會報錯，只是那次存檔完全沒有效果。

    這個鍵目前只出現在 basic_memory_agent 底下，所以全檔掃第一個就對。
    """
    for i, line in enumerate(lines):
        if not line.lstrip().startswith("llm_provider:"):
            continue
        indent, comment = _split_leaf(line)
        lines[i] = f"{indent}llm_provider: '{provider}'{comment}\n"
        return
    raise KeyError("llm_provider: line not found in conf.yaml")


def _point_llm_provider_at_openai_compatible(lines: list) -> None:
    """把 llm_provider 選擇器指向 openai_compatible_llm。

    保留給 tests/test_llm_config_write.py 這份特徵測試直接呼叫；邏輯已經搬到
    通用的 _point_llm_provider_at，這裡只是釘住舊呼叫端的簽名。
    """
    _point_llm_provider_at(lines, "openai_compatible_llm")


def _edit_provider_config(lines: list, provider: str, values: dict) -> None:
    """在既有的 ``lines`` 上套用 provider 設定的編輯，不讀檔、不寫檔。

    純粹的記憶體編輯步驟，從 ``write_provider_config`` 抽出來，讓它能跟其他
    編輯步驟（例如 ``_edit_use_mcpp``）在同一份 ``lines`` 上合併成一次寫入——
    見 ``write_provider_config_and_use_mcpp`` 的說明。

    provider 必須在 WRITABLE_PROVIDERS 裡——它會被拿去組 YAML 路徑，而呼叫端的
    值來自請求。

    values 可含 base_url / model / llm_api_key（字串葉節點）與 extra_body
    （巢狀）。**沒給的鍵不動**：自動設定只寫它有把握的東西，其餘留給使用者。
    """
    if provider not in WRITABLE_PROVIDERS:
        raise ValueError(f"Refusing to write unknown provider block: {provider!r}")

    start, end = nested_extent(
        lines, "character_config", "agent_config", "llm_configs", provider
    )

    for key in ("base_url", "model", "llm_api_key"):
        if key in values:
            end = upsert_leaf(
                lines, start, end, key, _quote_yaml_scalar(str(values[key]))
            )

    extra_body = values.get("extra_body")
    if extra_body:
        rendered = {k: _quote_yaml_scalar(str(v)) for k, v in extra_body.items()}
        end = upsert_nested_block(lines, start, end, "extra_body", rendered)

    _point_llm_provider_at(lines, provider)


def write_provider_config(provider: str, values: dict) -> None:
    """把設定寫進指定的供應商區塊，並把 llm_provider 指過去。

    只改該改的葉節點，其餘每一行、每一個註解、每一個 True 與 null 的寫法都原樣
    保留——ruamel 全份重新序列化會把它們正規化，在一個手寫的設定檔上那是幾十行
    無關的改動。ruamel 只拿來在動手之前驗證結構。

    編輯本身委派給 ``_edit_provider_config``；這裡只負責讀檔、驗證、寫檔這三個
    單獨呼叫時該做的事。需要跟別的編輯合成一次原子寫入時，不要疊呼叫這個函式
    （那樣會各自讀寫兩次，中間有半套生效的窗口），改用
    ``write_provider_config_and_use_mcpp``。
    """
    if provider not in WRITABLE_PROVIDERS:
        raise ValueError(f"Refusing to write unknown provider block: {provider!r}")

    _validate_path_with_ruamel(provider)

    lines = _read_conf_lines()
    _edit_provider_config(lines, provider, values)
    _write_conf(lines)


def _edit_use_mcpp(lines: list, enabled: bool) -> None:
    """在既有的 ``lines`` 上套用 use_mcpp 開關的編輯，不讀檔、不寫檔。

    這個鍵在 agent_settings.basic_memory_agent 底下，跟 llm_configs 是兄弟，
    所以走自己的 nested_extent。
    """
    start, end = nested_extent(
        lines,
        "character_config",
        "agent_config",
        "agent_settings",
        "basic_memory_agent",
    )
    # 裸的 True／False，不是字串——這份設定檔裡既有的寫法（見
    # player_route.py 的 rewrite_bool_leaf）都是這樣，conf_editor 存在的目的
    # 就是不要去改動使用者檔案原本的風格。
    upsert_leaf(lines, start, end, "use_mcpp", str(bool(enabled)))


def write_provider_config_and_use_mcpp(
    provider: str, values: dict, use_mcpp: bool
) -> None:
    """套用偵測到的模型設定：provider 區塊與 use_mcpp 兩個編輯要嘛都套上，要嘛
    都不動——給 apply-detected 這種「兩個鍵邏輯上是同一次操作」的呼叫端用。

    provider 區塊的編輯與 use_mcpp 的編輯各自都能對 conf.yaml 做到原子寫入
    （temp + os.replace），但把它們拆成兩次獨立呼叫並不是一次交易：第一個
    成功、第二個才丟例外的話（例如 basic_memory_agent 區塊結構壞掉讓
    nested_extent 丟 KeyError），conf.yaml 已經被改了——provider、model、
    llm_provider 指標都切過去了——但呼叫端拿到的是「寫入失敗」。使用者以為
    什麼都沒存到，其實存了一半，比乾脆全部不存更糟。

    做法：只讀一次 lines，兩個編輯都在記憶體裡的同一份 lines 上做完才真正
    寫檔一次——任何一步丟例外，檔案都還沒被碰過。
    """
    if provider not in WRITABLE_PROVIDERS:
        raise ValueError(f"Refusing to write unknown provider block: {provider!r}")

    _validate_path_with_ruamel(provider)

    lines = _read_conf_lines()
    _edit_provider_config(lines, provider, values)
    _edit_use_mcpp(lines, use_mcpp)
    _write_conf(lines)


def _write_openai_block(base_url: str, model: str, api_key: str) -> None:
    """把使用者填的端點／模型／金鑰寫進 openai_compatible_llm，並切換供應商。

    保留給 tests/test_llm_provider_write.py 與 tests/test_llm_config_write.py
    這兩份既有的特徵測試直接呼叫；行為完全交給通用的 write_provider_config，
    這裡只是釘住舊呼叫端的簽名，不重複邏輯。

    行為差異（相對於重構前）：舊版用 rewrite_str_leaf，三個葉節點裡任何一個在
    區塊裡找不到就丟 KeyError（"Could not locate keys [...]"）。現在委派給
    write_provider_config，走的是 upsert_leaf，找不到的葉節點會被**插入**，
    不丟例外——這是刻意的，不是疏漏。upsert_leaf 自己的 docstring 說得很清楚：
    UI 開得出來的設定就該存得下去，手寫的 conf.yaml 常常根本沒有那一行，舊版
    在這種情況直接丟 KeyError 是它自己的 bug，不是這裡要保留的行為。見
    tests/test_write_provider_config.py::test_write_openai_block_inserts_missing_leaf_instead_of_raising。
    """
    write_provider_config(
        "openai_compatible_llm",
        {"base_url": base_url, "model": model, "llm_api_key": api_key},
    )


# --- 端點 ------------------------------------------------------------------- #


def _bad(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"ok": False, "error": message})


def init_llm_config_route() -> APIRouter:
    """
    REST endpoints for the first-run BYO-LLM setup wizard. Localhost-only.

    - GET  /api/llm-config                -> current config, masked + is_configured
    - POST /api/llm-config                -> validate then save (ruamel round-trip)
    - GET  /api/llm-config/ollama-models  -> server-side Ollama probe (+ recommended)
    - POST /api/llm-config/ollama-pull    -> stream a model download (NDJSON progress)
    """
    router = APIRouter()

    @router.get("/api/llm-config")
    async def get_llm_config(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            data = _load_conf()
        except Exception as e:
            logger.error(f"llm-config read failed: {type(e).__name__}")
            return JSONResponse(
                status_code=500, content={"error": "could not read config"}
            )

        block = _get_openai_block(data)
        if block is None:
            return JSONResponse(
                status_code=500,
                content={"error": "openai_compatible_llm block missing in conf.yaml"},
            )

        configured = await _is_configured_for_conf(data)
        # What llm_provider ACTUALLY selects. This route reads and writes the
        # openai_compatible_llm block unconditionally, so when llm_provider names
        # something else (lmstudio_llm, ollama_llm, claude_llm...) the settings
        # tab shows a base_url and model that nothing is using — and anything the
        # user edits there silently fails to affect the conversation. Same trap as
        # a character pinning its own TTS engine. Report it so the UI can say so.
        active_provider = _get_llm_provider(data) or "openai_compatible_llm"
        return JSONResponse(
            {
                "provider": "openai_compatible_llm",
                "active_provider": str(active_provider),
                "base_url": (
                    str(block.get("base_url"))
                    if block.get("base_url") is not None
                    else ""
                ),
                "model": str(block.get("model"))
                if block.get("model") is not None
                else "",
                "api_key_masked": _mask_key(block.get("llm_api_key")),
                "has_real_key": _has_real_key(block),
                "is_configured": configured,
            }
        )

    @router.post("/api/llm-config")
    async def save_llm_config(request: Request):
        """驗證使用者填的組合，通過才寫進 conf.yaml。

        先驗證再寫入的順序很重要：填錯的設定寫進去，下次開機會直接起不來，而使用者
        當下只會看到「存好了」。
        """
        if not _is_local_request(request):
            return _forbidden()

        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return _bad("Invalid JSON body.")

        provider = str(body.get("provider", "")).strip().lower()
        if provider not in PROVIDER_DEFAULT_BASE_URL:
            return _bad("Unknown provider. Use openai, claude, gemini, or ollama.")

        base_url = _resolve_base_url_default(provider, body.get("base_url"))
        model = body.get("model")
        api_key = body.get("api_key")
        # 本機 Ollama 不需要金鑰，但下游的 client 要求非空，所以填一個公認的佔位值。
        if provider == "ollama" and not api_key:
            api_key = "ollama"

        for value, message in (
            (base_url, "Missing base_url."),
            (model, "Missing model name."),
            (api_key, "Missing API key."),
        ):
            if not value:
                return _bad(message)

        base_url = str(base_url).strip()
        model = str(model).strip()
        api_key = str(api_key)

        ok, err = await _validate_combo(base_url, model, api_key)
        if not ok:
            # err 已經去過金鑰了。這裡也不記金鑰。
            logger.info(f"[llm] validation failed for provider={provider}")
            return _bad(err)

        try:
            await asyncio.to_thread(
                write_provider_config,
                "openai_compatible_llm",
                {"base_url": base_url, "model": model, "llm_api_key": api_key},
            )
        except Exception as e:
            logger.error(f"[llm] write failed: {type(e).__name__}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not write config file."},
            )

        logger.info(f"[llm] saved (provider={provider}, model={model})")
        return JSONResponse(
            {
                "ok": True,
                "provider": "openai_compatible_llm",
                "model": model,
                "base_url": base_url,
                "api_key_masked": _mask_key(api_key),
                "restart_required": True,
            }
        )

    @router.get("/api/llm-config/ollama-models")
    async def get_ollama_models(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        result = await _probe_ollama_models()
        # 走 recommended_model()（讀 model_profiles.yaml 的 fallback），不要再用
        # 硬編碼的 RECOMMENDED_OLLAMA_MODEL——否則以後改了設定檔，這個端點還是
        # 回舊值，而且不會有任何徵兆。
        ram = await asyncio.to_thread(total_ram_bytes)
        result["recommended"] = recommended_model(ram)
        return JSONResponse(result)

    # 同時只允許一個安裝在跑。使用者連按兩下、或開了兩個分頁，不該跑出兩個安裝程式。
    install_lock = asyncio.Lock()

    @router.post("/api/llm-config/ollama-install")
    async def install_ollama(request: Request):
        """一鍵安裝 Ollama，進度用 NDJSON 串流回傳，事件格式同 ollama-pull。

        會下載並執行安裝程式，所以跟其他寫入端點一樣只接受本機請求。
        """
        if not _is_local_request(request):
            return _forbidden()

        def line(event: dict) -> str:
            return json.dumps(event) + "\n"

        async def stream():
            if install_lock.locked():
                yield line(
                    {"status": "error", "error": "Ollama is already being installed."}
                )
                return
            async with install_lock:
                try:
                    async for event in ollama_installer.install():
                        yield line(event)
                except ollama_installer.InstallError as e:
                    yield line({"status": "error", "error": str(e)})
                except httpx.TimeoutException:
                    yield line(
                        {
                            "status": "error",
                            "error": "The download stalled. Check your connection and try again.",
                        }
                    )
                except Exception as e:
                    logger.warning(f"ollama-install failed: {type(e).__name__}: {e}")
                    yield line(
                        {
                            "status": "error",
                            "error": "Installing Ollama failed. Try again, or download it from ollama.com.",
                        }
                    )

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @router.post("/api/llm-config/ollama-pull")
    async def pull_ollama_model(request: Request):
        """幫使用者下載模型，把 Ollama 的進度原樣轉給前端。

        一路轉發進度是刻意的：下載動輒幾分鐘，畫面上如果只有一個轉圈圈，人會
        以為當掉了。
        the browser so the wizard can show a progress bar. This lets a non-technical
        player get the recommended local brain without ever opening a terminal."""
        if not _is_local_request(request):
            return _forbidden()
        try:
            body = await request.json()
        except Exception:
            body = {}
        model = str(body.get("model") or RECOMMENDED_OLLAMA_MODEL).strip()
        if not model:
            return JSONResponse(
                status_code=400, content={"error": "Missing model name."}
            )

        async def stream():
            # 整個下載可能好幾分鐘，所以不設總逾時。但兩件事要管：連線階段要有
            # 上限，以及**卡住的下載**要偵測得出來。Ollama 的進度是密集送的，
            # 一段時間沒有任何一行進來就代表連線已經斷了。沒有這道判斷的話，
            # 網路不穩時精靈會永遠轉下去。
            connect_timeout = httpx.Timeout(None, connect=15.0)
            idle_timeout = 120.0  # 這麼久沒有任何進度就當作斷了
            try:
                async with httpx.AsyncClient(timeout=connect_timeout) as client:
                    async with client.stream(
                        "POST",
                        OLLAMA_PULL_URL,
                        json={"model": model, "stream": True},
                    ) as resp:
                        if resp.status_code != 200:
                            detail = (await resp.aread()).decode("utf-8", "replace")[
                                :300
                            ]
                            yield (
                                json.dumps(
                                    {
                                        "status": "error",
                                        "error": f"Ollama returned {resp.status_code}. {detail}".strip(),
                                    }
                                )
                                + "\n"
                            )
                            return
                        line_iter = resp.aiter_lines().__aiter__()
                        while True:
                            try:
                                line = await asyncio.wait_for(
                                    line_iter.__anext__(), timeout=idle_timeout
                                )
                            except StopAsyncIteration:
                                break
                            except asyncio.TimeoutError:
                                yield (
                                    json.dumps(
                                        {
                                            "status": "error",
                                            "error": "Download stalled (no progress for a while). Check your connection and try again — it resumes from where it left off.",
                                        }
                                    )
                                    + "\n"
                                )
                                return
                            if line.strip():
                                yield line + "\n"
            except Exception as e:
                logger.info(f"ollama-pull failed: {type(e).__name__}")
                yield (
                    json.dumps(
                        {
                            "status": "error",
                            "error": "Could not reach Ollama. Is the Ollama app running?",
                        }
                    )
                    + "\n"
                )

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    @router.get("/api/llm-config/detect")
    async def detect_models(request: Request):
        """列出本機兩個推論端上可用的模型。

        兩邊都連不上不是錯誤——精靈要能顯示「請先裝一個」而不是白畫面。所以
        一律回 200，用 *_available 告訴前端發生了什麼。

        *_available 是**可達性**（daemon 連不連得上），不是「有沒有模型」。
        這兩者曾經被 bool(models) 混在一起——「連得上但一顆模型都沒下載」
        跟「根本沒裝」在那個寫法下是同一個值，前端因此永遠分不出「請下載一個
        模型」跟「請先安裝」這兩種完全不同的建議（first-run-model-detection
        Task 9 接上前端才發現）。probe_lmstudio()／probe_ollama() 把兩件事分開
        回傳，這裡才能各自轉成正確的旗標。
        """
        if not _is_local_request(request):
            return _forbidden()

        # 兩個 probe 互相獨立，沒有理由排隊等——循序做的話，其中一個推論端
        # 「有在聽但卡住」時，最壞延遲會從 max(兩者) 變成 sum(兩者)。
        (lms_reachable, lms), (olm_reachable, olm), ram = await asyncio.gather(
            asyncio.to_thread(probe_lmstudio, LMSTUDIO_DEFAULT_BASE_URL),
            asyncio.to_thread(probe_ollama, OLLAMA_DEFAULT_BASE_URL),
            asyncio.to_thread(total_ram_bytes),
        )

        return JSONResponse(
            {
                "models": [asdict(m) for m in [*lms, *olm]],
                "lmstudio_available": lms_reachable,
                "ollama_available": olm_reachable,
                # 只有連不上時才有意義：用來分「請下載 Ollama」和「請打開 Ollama」。
                "ollama_installed": olm_reachable or ollama_installed(),
                "ollama_install_supported": ollama_installer.supported(),
                "recommended_pull": recommended_model(ram),
            }
        )

    @router.post("/api/llm-config/apply-detected")
    async def apply_detected(request: Request):
        """把使用者選的那顆模型寫進設定，並套用它需要的必要設定。"""
        if not _is_local_request(request):
            return _forbidden()
        try:
            body = await request.json()
        except Exception:
            body = {}

        backend = str(body.get("backend") or "").strip().lower()
        model_id = str(body.get("model") or "").strip()
        provider = _BACKEND_TO_PROVIDER.get(backend)
        if not provider or not model_id:
            return _bad("Unknown backend or missing model name.")

        # model 是請求可控的。只接受這次真的偵測得到的那些——不讓任意字串走到
        # 寫檔案那一步。
        if backend == "lmstudio":
            found = await asyncio.to_thread(
                list_lmstudio_models, LMSTUDIO_DEFAULT_BASE_URL
            )
        else:
            found = await asyncio.to_thread(list_ollama_models, OLLAMA_DEFAULT_BASE_URL)
        chosen = next((m for m in found if m.id == model_id), None)
        if chosen is None:
            return _bad(f"Model {model_id!r} is no longer available on {backend}.")

        # id 會被逐字寫進 conf.yaml。它今天只可能來自本機推論端回報的清單
        # （見上面的比對），不是使用者直接輸入，但控制字元（尤其是換行）一旦
        # 混進 id，就能在寫檔時多插出任意一行 YAML——窄，但不是不可能：一個
        # 被亂改過或本身有 bug 的 localhost 行程就辦得到。這裡直接拒絕，堵死
        # 這條路，不必去信任偵測到的字串長什麼樣子。
        if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in chosen.id):
            return _bad(f"Model id {chosen.id!r} contains invalid control characters.")

        # Ollama 的能力資訊要逐顆問，留到這裡才問（見 model_probe）。
        #
        # describe_ollama_model 問不到（3 秒逾時、Ollama 正在載入大模型時的
        # 暫時性 500）不代表這顆模型沒有工具能力，只代表「還沒問到」。此時
        # chosen 仍是列表階段那筆記錄，它的 supports_tools 是 False——但那個
        # False 是「還沒問」的預設值，不是探測結果。capability_known 記住這
        # 件事，讓下面寫檔那一步知道要不要動 use_mcpp。
        capability_known = True
        if backend == "ollama":
            detailed = await asyncio.to_thread(
                describe_ollama_model, chosen.base_url, chosen.id
            )
            if detailed is not None:
                chosen = detailed
            else:
                capability_known = False

        ok, message = await _validate_combo(chosen.base_url, chosen.id, "")
        if not ok:
            return _bad(message)

        profile = profile_for(chosen)
        values = {"base_url": chosen.base_url, "model": chosen.id}
        if profile:
            values["extra_body"] = profile["extra_body"]

        try:
            if capability_known:
                # provider 區塊與 use_mcpp 是同一次操作的兩個鍵，走合併入口
                # 一次讀、一次寫——避免第一個編輯落地、第二個才失敗時，
                # conf.yaml 已經半套生效但回應卻說寫入失敗
                # （見 write_provider_config_and_use_mcpp）。
                await asyncio.to_thread(
                    write_provider_config_and_use_mcpp,
                    provider,
                    values,
                    chosen.supports_tools,
                )
            else:
                # 沒問到能力就不動 use_mcpp，留著使用者原本在 Settings 裡的
                # 選擇——一次 fail-soft 的探測失敗不該變成一次確定的設定
                # 變更。
                await asyncio.to_thread(write_provider_config, provider, values)
        except Exception as e:
            logger.warning(f"apply-detected write failed: {type(e).__name__}: {e}")
            return _bad("Could not write conf.yaml.")

        return JSONResponse(
            {
                "ok": True,
                "applied": {
                    "provider": provider,
                    "model": chosen.id,
                    "is_vlm": chosen.is_vlm,
                    "supports_tools": chosen.supports_tools,
                    "max_context": chosen.max_context,
                },
                "note": profile["note"] if profile else None,
            }
        )

    return router
