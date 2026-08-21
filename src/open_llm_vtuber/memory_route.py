"""長期記憶的設定頁後端：讓使用者不必手改 YAML 就能管理 AI 記住的東西。

記憶是每個角色一份（chat_history/<conf_uid>/core_memory.md），所以每個端點都以
conf_uid 為鍵。前端本來就從 WebSocket 的 set-model-and-conf 知道當前角色，會明確
帶上；沒帶就退回 conf.yaml 裡的基礎角色。

安全上有兩道，兩道都不能省：

- 只接受本機請求（連同代理標頭的檢查）。
- conf_uid 在被組成任何檔案路徑之前，先擋掉路徑符號、再比對已知角色的集合。
  這是使用者送來的字串，直接拿去接路徑等於開放任意檔案截斷。

開關與兩個數值存在 conf.yaml 的 character_config 底下，寫入走 conf_editor 的
就地改寫——整份重新序列化會把使用者寫的註解洗掉。

「清空」是把檔案截斷成空的，不刪檔也不動對話紀錄；使用者要的是「忘掉」，不是
「把歷史消滅」。

行為契約由 tests/test_memory_route_reads.py 與 tests/test_memory_conf_leaf_insert.py
釘住。
"""

import os
import re
import asyncio
from typing import Any, Optional

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse
from loguru import logger

from .api_guard import is_trusted_request as _is_local_request, forbidden as _forbidden, make_yaml as _make_yaml

from .conf_editor import (
    CONF_PATH,
    character_config_extent as _character_config_extent,
    find_block_extent as _find_block_extent,
    read_conf_lines as _read_conf_lines,
    rewrite_int_leaf as _rewrite_int_leaf,
    upsert_leaf as _upsert_leaf,
    write_conf as _write_conf,
)

from .character_route import _existing_conf_uids
from .config_manager.utils import read_yaml
from . import memory_core


# --------------------------------------------------------------------------- #
# Read helpers
# --------------------------------------------------------------------------- #


def _load_conf_plain() -> Any:
    """Round-trip 讀 conf.yaml（只用來讀純量值）。"""
    yaml = _make_yaml()
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        return yaml.load(f)


def _character_setting(key: str, default: Any, coerce=None) -> Any:
    """讀 character_config 底下的一個設定，讀不到就回程式端的預設值。

    四個設定原本各自寫一遍同樣的 try／read／dig／default，四份都要記得 fail-soft。
    收成一個之後，「conf.yaml 有問題不可以讓設定頁打不開」這條保證只需要對一次。

    ``coerce`` 用來把讀到的值夾進合法範圍——UI 顯示的數字永遠要在範圍內，就算
    有人手動把 conf.yaml 改成離譜的值。
    """
    try:
        data = read_yaml(CONF_PATH) or {}
        value = data.get("character_config", {}).get(key)
    except Exception:
        return default
    if value is None:
        return default
    return coerce(value) if coerce else value


def _base_conf_uid() -> Optional[str]:
    """conf.yaml 裡基礎角色的 conf_uid（沒指定角色時的退路）。"""
    uid = _character_setting("conf_uid", None)
    return str(uid) if uid else None


def _memory_enabled_from_conf() -> bool:
    """長期記憶開著沒有。缺鍵時預設開啟，跟 Pydantic 的預設一致。"""
    return bool(_character_setting("long_term_memory_enabled", True))


def _cap_from_conf() -> int:
    """記憶字數上限，夾進 [CAP_MIN, CAP_MAX]。"""
    return _character_setting(
        "core_memory_max_chars", memory_core.CAP_CHARS, memory_core._clamp_cap
    )


def _interval_from_conf() -> int:
    """整理頻率，夾進 memory_core 允許的集合。"""
    return _character_setting(
        "memory_consolidation_interval",
        memory_core.CONSOLIDATE_INTERVAL_DEFAULT,
        memory_core._clamp_interval,
    )


def _resolve_conf_uid(supplied: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """驗證前端送來的 conf_uid，沒帶就退回基礎角色。.

    Returns ``(conf_uid, error)``. ``error`` is non-None when the supplied uid is
    unknown (rejected to prevent arbitrary-path access). A falsy ``supplied`` falls
    back to the base conf_uid without error.
    """
    if supplied is not None and str(supplied).strip():
        uid = str(supplied).strip()
        # 路徑符號在比對已知集合「之前」就擋掉——這是安全防線的第一道。
        if os.sep in uid or "/" in uid or "\\" in uid or ".." in uid:
            return None, "Invalid conf_uid."
        known = _existing_conf_uids()
        if uid not in known:
            return None, "Unknown conf_uid."
        return uid, None
    # 沒指定就用底稿的角色。
    base = _base_conf_uid()
    if not base:
        return None, "No conf_uid available."
    return base, None


# --- 寫設定 ----------------------------------------------------------------- #
# --------------------------------------------------------------------------- #


def _write_memory_enabled(enabled: bool) -> bool:
    """開關長期記憶。

    The leaf must already exist in conf.yaml (added by hand). Atomic + one-time .bak.
    Returns True on success.
    """
    lines = _read_conf_lines()
    cc_start, cc_end = _character_config_extent(lines)
    _upsert_leaf(lines, cc_start, cc_end, "long_term_memory_enabled", str(bool(enabled)))
    _write_conf(lines)
    return True





def _write_core_memory_cap(cap: int) -> bool:
    """設定記憶的字數上限。

    The leaf must already exist in conf.yaml. Atomic + one-time .bak. Returns True.
    """
    lines = _read_conf_lines()
    cc_start, cc_end = _character_config_extent(lines)
    _upsert_leaf(lines, cc_start, cc_end, "core_memory_max_chars", str(int(cap)))
    _write_conf(lines)
    return True


def _write_consolidation_interval(interval: int) -> bool:
    """設定記憶整理的頻率。

    The leaf must already exist in conf.yaml. Atomic + one-time .bak. Returns True.
    (perf_route exposes the same setting via /api/perf/consolidation; this mirror lets
    the memory tab save it through the memory namespace the FE already calls.)
    """
    lines = _read_conf_lines()
    cc_start, cc_end = _character_config_extent(lines)
    _upsert_leaf(
        lines, cc_start, cc_end, "memory_consolidation_interval", str(int(interval))
    )
    _write_conf(lines)
    return True


# --------------------------------------------------------------------------- #
# 端點共用的前置作業
# --------------------------------------------------------------------------- #


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"ok": False, "error": message})


async def _parse_body(request: Request) -> tuple[Optional[dict], Optional[JSONResponse]]:
    """讀出 JSON body，順便驗證它是個物件。

    回傳 (body, 錯誤回應)——其中一個一定是 None。六個端點原本各自寫一遍
    try/except 加 isinstance 檢查，錯誤訊息還得手動保持一致。
    """
    try:
        body = await request.json()
    except Exception:
        return None, _error(400, "Invalid JSON body.")
    if not isinstance(body, dict):
        return None, _error(400, "Invalid JSON body.")
    return body, None


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


def _resolved_uid(body: dict):
    """從 body 取出並驗證 conf_uid。回傳 (conf_uid, 錯誤回應)。"""
    conf_uid, err = _resolve_conf_uid(body.get("conf_uid"))
    if err:
        return None, _error(400, err)
    return conf_uid, None


async def _write_or_error(fn, *args, what: str):
    """在執行緒裡跑一個寫入動作；失敗時記 log 並回統一的 500。

    寫設定檔失敗的處理六個端點都一樣：記下真正的例外（給我們看）、回一句
    使用者看得懂的話（不外洩內部細節）。
    """
    try:
        await asyncio.to_thread(fn, *args)
        return None
    except Exception as e:
        logger.error(f"[memory] {what} failed: {type(e).__name__}: {e}")
        return _error(500, "Could not write config file.")


# --------------------------------------------------------------------------- #
# Route factory
# --------------------------------------------------------------------------- #


def init_memory_route() -> APIRouter:
    """長期記憶設定頁的 REST 端點。只接受本機請求。

    - GET  /api/memory?conf_uid=<uid>   記憶開關、內容、字數與各項界限
    - POST /api/memory                  整份覆寫記憶內容（使用者手動修正）
    - POST /api/memory/toggle           開關長期記憶
    - POST /api/memory/clear            清空記憶
    - POST /api/memory/cap              設定字數上限
    - POST /api/memory/consolidation    設定整理頻率

    每個寫入端點的回應都帶 restart_required：agent 的 system prompt 在 init 時就
    烤好了，已經注入的記憶要等重選角色或重啟才會完全反映。存檔本身是即時的，
    下一輪整理讀到的就是新值。
    """
    router = APIRouter()

    @router.get("/api/memory")
    async def get_memory(request: Request):
        if not _is_local_request(request):
            return _forbidden()

        conf_uid, err = _resolve_conf_uid(request.query_params.get("conf_uid"))
        if err:
            return JSONResponse(status_code=400, content={"error": err})

        content = memory_core.load_core_memory(conf_uid)
        return JSONResponse(
            {
                "conf_uid": conf_uid,
                "enabled": _memory_enabled_from_conf(),
                "content": content,
                "exists": os.path.isfile(memory_core.core_memory_path(conf_uid)),
                "char_count": len(content),
                # 界限一律從後端送，UI 不要自己寫死一份——後端調整了那份副本不會
                # 跟著動，畫面會強制一個伺服器早就不用的範圍，而且不會報錯。
                "cap": _cap_from_conf(),
                "cap_min": memory_core.CAP_MIN,
                "cap_max": memory_core.CAP_MAX,
                "consolidation_interval": _interval_from_conf(),
                "consolidation_interval_choices": list(
                    memory_core.CONSOLIDATE_INTERVAL_CHOICES
                ),
            }
        )

    @router.post("/api/memory")
    async def save_memory(request: Request):
        """把記憶內容整份換成使用者編輯過的版本。

        讓不會改設定檔的人也能直接修掉 AI 記錯或不想被記住的事。超過上限的內容
        照存不截斷——偷偷砍掉使用者打的字比超長更意外，下一輪整理本來就會提煉。
        """
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad

        content = body.get("content")
        if not isinstance(content, str):
            return _error(400, "'content' must be a string.")

        cap = _cap_from_conf()
        if not await asyncio.to_thread(
            memory_core.save_core_memory, conf_uid, content, cap
        ):
            return _error(500, "Could not save core memory.")

        # 讀回真正存下去的內容，讓 UI 的字數是誠實的。
        stored = memory_core.load_core_memory(conf_uid)
        logger.info(f"[memory] manually saved (conf_uid={conf_uid})")
        return JSONResponse(
            {
                "ok": True,
                "conf_uid": conf_uid,
                "char_count": len(stored),
                "cap": cap,
                "restart_required": True,
            }
        )

    @router.post("/api/memory/toggle")
    async def toggle_memory(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad
        if "enabled" not in body:
            return _error(400, "Missing 'enabled' boolean.")

        # conf_uid 驗證過只為了回應的形狀；開關本身是基礎 character_config 的，
        # 那是執行中的設定唯一會讀的地方。
        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad

        enabled = bool(body["enabled"])
        bad = await _write_or_error(_write_memory_enabled, enabled, what="toggle write")
        if bad:
            return bad

        logger.info(f"[memory] toggle saved (enabled={enabled})")
        return JSONResponse(
            {
                "ok": True,
                "conf_uid": conf_uid,
                "enabled": enabled,
                "restart_required": True,
            }
        )

    @router.post("/api/memory/clear")
    async def clear_memory(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad

        if not await asyncio.to_thread(memory_core.clear_core_memory, conf_uid):
            return _error(500, "Could not clear core memory.")

        logger.info(f"[memory] cleared (conf_uid={conf_uid})")
        return JSONResponse({"ok": True, "conf_uid": conf_uid, "cleared": True})

    @router.post("/api/memory/cap")
    async def set_cap(request: Request):
        """設定記憶的字數上限（[CAP_MIN, CAP_MAX] 之間）。"""
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        conf_uid, bad = _resolved_uid(body)
        if bad:
            return bad

        cap, bad = _bounded_int(body, "cap", memory_core.CAP_MIN, memory_core.CAP_MAX)
        if bad:
            return bad

        bad = await _write_or_error(_write_core_memory_cap, cap, what="cap write")
        if bad:
            return bad

        logger.info(f"[memory] cap saved (cap={cap})")
        return JSONResponse(
            {
                "ok": True,
                "conf_uid": conf_uid,
                "cap": cap,
                "restart_required": True,
            }
        )

    @router.post("/api/memory/consolidation")
    async def set_consolidation(request: Request):
        """設定整理頻率（每 N 輪整理一次，N 限定在允許的集合裡）。

        1 = 每輪（預設）；3／5 可以把整理用的 LLM 呼叫省一半以上，適合弱機。
        """
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        conf_uid, bad = _resolved_uid(body)
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

        logger.info(f"[memory] consolidation interval saved (interval={interval})")
        return JSONResponse(
            {
                "ok": True,
                "conf_uid": conf_uid,
                "consolidation_interval": interval,
                "restart_required": True,
            }
        )

    return router
