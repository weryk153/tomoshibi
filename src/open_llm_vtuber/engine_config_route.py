"""設定頁的「由 AI Character Engine 驅動對話」：開關，加上背景工作每幾輪跑一次。

跟 player_route 的 use_mcpp 同一套：直接就地改寫 conf.yaml、保留註解；conf.yaml
只在啟動時讀一次，所以回應一律帶 restart_required。引擎裝不裝得起來也在這裡
回答，讓畫面能說明為什麼開關是灰的，而不是存了之後重啟才炸。
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from typing import Any

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse

from .api_guard import (
    forbidden as _forbidden,
    is_trusted_request as _is_local_request,
    make_yaml as _make_yaml,
)
from .conf_editor import (
    CONF_PATH,
    block_extent,
    read_conf_lines,
    rewrite_str_leaf,
    upsert_leaf,
    upsert_nested_block,
    write_conf,
)

ENGINE_CHOICE = "character_engine_agent"
BASIC_CHOICE = "basic_memory_agent"
# 畫面開得出來的幾個；其餘（timeout、goal_max_age_days…）留在 YAML。
EVERY_KEYS = (
    "emotion_every",
    "memory_every",
    "goal_every",
    "reflection_every",
    "goals_shown",
    "thoughts_shown",
)
EVERY_DEFAULTS = {
    "emotion_every": 1,
    "memory_every": 2,
    "goal_every": 4,
    "reflection_every": 6,
    "goals_shown": 3,
    "thoughts_shown": 2,
}
EVERY_MAX = 99


def _load_conf() -> Any:
    yaml = _make_yaml()
    with open(CONF_PATH, "r", encoding="utf-8") as f:
        return yaml.load(f)


def _agent_config(data: Any) -> dict:
    return ((data.get("character_config") or {}).get("agent_config")) or {}


def read_engine_settings() -> dict:
    data = _load_conf()
    agent_config = _agent_config(data)
    block = (agent_config.get("agent_settings") or {}).get(ENGINE_CHOICE) or {}
    settings = {
        "enabled": agent_config.get("conversation_agent_choice") == ENGINE_CHOICE
    }
    for key in EVERY_KEYS:
        settings[key] = _clamp(block.get(key), EVERY_DEFAULTS[key])
    return settings


def _clamp(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(0, min(EVERY_MAX, number))


def write_engine_settings(changes: dict) -> None:
    """只寫送來的那幾個；沒送的不動。數字超出範圍就夾住，不是數字就略過。"""
    lines = read_conf_lines()
    agent_start, agent_end = block_extent(lines, "agent_config")

    if "enabled" in changes:
        choice = ENGINE_CHOICE if changes["enabled"] else BASIC_CHOICE
        if not rewrite_str_leaf(
            lines, agent_start, agent_end, "conversation_agent_choice", choice
        ):
            agent_end = upsert_leaf(
                lines,
                agent_start,
                agent_end,
                "conversation_agent_choice",
                f"'{choice}'",
            )

    numbers = {}
    for key in EVERY_KEYS:
        if key in changes:
            try:
                numbers[key] = str(_clamp(int(changes[key]), EVERY_DEFAULTS[key]))
            except (TypeError, ValueError):
                continue
    if numbers:
        settings_start, settings_end = block_extent(
            lines, "agent_settings", start_from=agent_start
        )
        if settings_start >= agent_end:
            raise KeyError("agent_settings: not found inside agent_config")
        upsert_nested_block(lines, settings_start, settings_end, ENGINE_CHOICE, numbers)
    write_conf(lines)


def _engine_importable() -> bool:
    return importlib.util.find_spec("ai_character_engine") is not None


def engine_availability() -> tuple[bool, str]:
    """引擎用不用得起來，用不起來是為什麼——給畫面顯示在灰掉的開關旁邊。"""
    if sys.version_info < (3, 11):
        return False, (
            f"AI Character Engine needs Python 3.11 or newer; this server runs "
            f"{sys.version.split()[0]}."
        )
    if not _engine_importable():
        return False, (
            "The ai-character-engine package is not installed in this server's "
            "environment."
        )
    return True, ""


async def _parse_body(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = None
    if not isinstance(body, dict):
        return None, JSONResponse(
            status_code=400, content={"ok": False, "error": "Invalid JSON body."}
        )
    return body, None


def init_engine_config_route() -> APIRouter:
    router = APIRouter()

    @router.get("/api/agent-config/character-engine")
    async def get_engine_settings(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        try:
            settings = await asyncio.to_thread(read_engine_settings)
        except Exception as e:
            logger.error(f"[engine-config] read failed: {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=500, content={"error": "could not read config"}
            )
        available, reason = engine_availability()
        return JSONResponse({**settings, "available": available, "reason": reason})

    @router.post("/api/agent-config/character-engine")
    async def save_engine_settings(request: Request):
        if not _is_local_request(request):
            return _forbidden()
        body, bad = await _parse_body(request)
        if bad:
            return bad
        changes = {k: body[k] for k in ("enabled", *EVERY_KEYS) if k in body}
        if changes.get("enabled"):
            available, reason = engine_availability()
            if not available:
                return JSONResponse(
                    status_code=400, content={"ok": False, "error": reason}
                )
        try:
            await asyncio.to_thread(write_engine_settings, changes)
            settings = await asyncio.to_thread(read_engine_settings)
        except Exception as e:
            logger.error(f"[engine-config] write failed: {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not write config file."},
            )
        logger.info(f"[engine-config] saved {sorted(changes)}")
        return JSONResponse({"ok": True, **settings, "restart_required": True})

    return router
