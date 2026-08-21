"""玩家層級的設定：跟「你」有關、而不是跟某個角色有關的那些。

這些設定的共同點是它們跨越所有角色——換角色不會換掉它們：

- **玩家語言**（system_config.player_language）：沒有指定語言的角色會用它。
  角色自己的 reply_language 蓋過它，因為語言屬於角色本身（紅莉栖是日本人，
  貓娘不是），全域設定只是「沒特別指定時的預設」。
- **玩家提示**（system_config.player_prompt）：一句關於你的話，會被注入每一個
  角色的 system prompt。
- **工具開關**（…basic_memory_agent.use_mcpp）：讓角色能用 MCP 工具（網路搜尋等）。

這幾個原本住在 translator_route 裡——那個模組長成了雜物櫃，翻譯設定跟玩家設定
擠在一起，還順便擁有全域的 conf.yaml 編輯原語。搬出來之後兩邊都只剩自己的事。

寫入一律走 conf_editor 的就地改寫，保留使用者在 conf.yaml 裡寫的註解。
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Optional

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse

from .conf_editor import (
    block_extent,
    read_conf_lines,
    rewrite_bool_leaf,
    system_config_extent,
    upsert_leaf,
    write_conf,
)
from .api_guard import forbidden as _forbidden, is_trusted_request as _is_local_request, make_yaml as _make_yaml
from .conf_editor import CONF_PATH


def _load_conf() -> Any:
    yaml = _make_yaml()
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        return yaml.load(f)


def _system_setting(key: str) -> str:
    """讀 system_config 底下的一個字串設定；讀不到就回空字串。"""
    data = _load_conf()
    block = data.get("system_config") or {}
    value = block.get(key)
    return str(value) if value is not None else ""


def _quote(value: str) -> str:
    """YAML 單引號純量，內部的單引號要成對跳脫。"""
    return "'" + str(value).replace("'", "''") + "'"


def _write_system_setting(key: str, value: str) -> None:
    """就地寫入 system_config 底下的一個字串設定（沒有那行就補上）。"""
    lines = read_conf_lines()
    start, end = system_config_extent(lines)
    upsert_leaf(lines, start, end, key, _quote(value))
    write_conf(lines)


def _write_use_mcpp(enabled: bool) -> None:
    """寫入巢狀在三層底下的 use_mcpp 布林。

    路徑是 character_config → agent_config → agent_settings → basic_memory_agent。
    一層一層往下找，每層找不到就丟 KeyError——這比讓它靜靜寫到錯的地方好。
    """
    lines = read_conf_lines()
    settings_start, settings_end = block_extent(lines, "agent_settings")
    agent_start, agent_end = block_extent(
        lines, "basic_memory_agent", start_from=settings_start
    )
    if agent_start >= settings_end:
        raise KeyError("basic_memory_agent: not found inside agent_settings")

    # YAML 布林要寫成裸的 True／False，加引號就變成字串了。
    if not rewrite_bool_leaf(lines, agent_start, agent_end, "use_mcpp", enabled):
        upsert_leaf(lines, agent_start, agent_end, "use_mcpp", str(bool(enabled)))
    write_conf(lines)


async def _parse_body(request: Request) -> tuple[Optional[dict], Optional[JSONResponse]]:
    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        return None, JSONResponse(
            status_code=400, content={"ok": False, "error": "Invalid JSON body."}
        )
    return body, None


async def _save(fn, value, *, what: str, payload: dict) -> JSONResponse:
    """統一的寫入路徑：丟到執行緒、失敗回 500、成功回帶 restart_required 的結果。

    這三個設定都在 server 啟動時被烤進 system prompt，所以存檔是即時的、生效要
    等重啟——回應一律帶著這個事實，前端才有辦法誠實地告訴使用者。
    """
    try:
        await asyncio.to_thread(fn, value)
    except Exception as e:
        logger.error(f"[player] {what} write failed: {type(e).__name__}: {e}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Could not write config file."},
        )
    logger.info(f"[player] {what} saved")
    return JSONResponse({"ok": True, **payload, "restart_required": True})


def _read_or_error(fn, *, what: str, key: str) -> JSONResponse:
    try:
        return JSONResponse({key: fn()})
    except Exception as e:
        logger.error(f"[player] {what} read failed: {type(e).__name__}")
        return JSONResponse(
            status_code=500, content={"error": "could not read config"}
        )


def init_player_route() -> APIRouter:
    """玩家層級設定的 REST 端點。只接受本機請求。"""
    router = APIRouter()

    @router.post("/api/player-language")
    async def save_player_language(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        language = str(body.get("language") or "").strip()
        return await _save(
            lambda v: _write_system_setting("player_language", v),
            language,
            what="player-language",
            payload={"language": language},
        )

    @router.get("/api/player-prompt")
    async def get_player_prompt(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        return _read_or_error(
            lambda: _system_setting("player_prompt"),
            what="player-prompt",
            key="prompt",
        )

    @router.post("/api/player-prompt")
    async def save_player_prompt(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        # 這是一句短指示。換行全部壓成空白，讓它在 conf.yaml 裡維持單行純量——
        # 多行的 block scalar 會把手寫的檔案攪得很亂。
        prompt = re.sub(r"\s*\n\s*", " ", str(body.get("prompt") or "")).strip()
        return await _save(
            lambda v: _write_system_setting("player_prompt", v),
            prompt,
            what="player-prompt",
            payload={"prompt": prompt},
        )

    @router.get("/api/agent-config/use-mcpp")
    async def get_use_mcpp(request: Request):
        if not _is_local_request(request):
            return _forbidden()

        def read() -> bool:
            data = _load_conf()
            agent = (
                ((data.get("character_config") or {}).get("agent_config") or {}).get(
                    "agent_settings"
                )
                or {}
            ).get("basic_memory_agent") or {}
            return bool(agent.get("use_mcpp", False))

        return _read_or_error(read, what="use-mcpp", key="use_mcpp")

    @router.post("/api/agent-config/use-mcpp")
    async def save_use_mcpp(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad

        enabled = bool(body.get("use_mcpp"))
        return await _save(
            _write_use_mcpp,
            enabled,
            what="use-mcpp",
            payload={"use_mcpp": enabled},
        )

    return router
