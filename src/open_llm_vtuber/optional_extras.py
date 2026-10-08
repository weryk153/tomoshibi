"""選裝套件：預設不裝、在設定頁一鍵裝（目前是 faster-whisper）。

桌面版每次啟動都跑 `uv sync`（backend-manager.ts），只裝鎖定清單裡的東西；直接 pip
裝進去，下次開 App 就被清掉。所以：

- 裝過的選裝套件記在後端資料夾（cwd）的 extras.json；桌面版啟動同步時讀它，每個都
  帶 `--extra <名字>`。
- 安裝也用 `uv sync --frozen --inexact --no-dev --extra ...`：照鎖定的版本裝，
  `--inexact` 不動原本就在的其他套件。uv 的位置由桌面版用 TOMOSHIBI_UV 傳進來；開發
  時用 PATH 上的 uv。

- GET  /api/extras/{名字}          -> 裝好了沒、正在裝嗎、大概要下載多少
- POST /api/extras/{名字}/install  -> 安裝，進度用 NDJSON 串流（一行一則 uv 的輸出）
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import os
import shutil
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse, StreamingResponse

from .api_guard import forbidden as _forbidden, is_trusted_request as _is_local_request

# 名字（pyproject 的 optional-dependencies）→ 裝好之後 import 得到的模組、大概的下載量。
EXTRAS: dict[str, dict[str, Any]] = {
    "faster_whisper": {"module": "faster_whisper", "download_mb": 150},
}
EXTRAS_FILE = "extras.json"


def available(extra: str) -> bool:
    """這個選裝套件現在 import 得到嗎。"""
    module = EXTRAS.get(extra, {}).get("module")
    if not module:
        return False
    importlib.invalidate_caches()
    return importlib.util.find_spec(module) is not None


def remembered() -> list[str]:
    """這台裝過的選裝套件（只認得 EXTRAS 裡的名字）。"""
    try:
        with open(EXTRAS_FILE, encoding="utf-8") as f:
            names = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(names, list):
        return []
    return [name for name in dict.fromkeys(names) if name in EXTRAS]


def remember(extra: str) -> None:
    names = remembered()
    if extra in EXTRAS and extra not in names:
        names.append(extra)
    tmp = EXTRAS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(names, f)
    os.replace(tmp, EXTRAS_FILE)


def sync_command(extras: list[str]) -> Optional[list[str]]:
    """裝這些選裝套件的 uv 指令；找不到 uv 是 None。"""
    uv = os.environ.get("TOMOSHIBI_UV") or shutil.which("uv")
    if not uv:
        return None
    command = [uv, "sync", "--frozen", "--inexact", "--no-dev", "--no-progress"]
    for extra in dict.fromkeys(extras):
        command += ["--extra", extra]
    return command


async def install(extra: str) -> AsyncIterator[dict[str, Any]]:
    """裝一個選裝套件（連同之前裝過的一起同步）；最後一則是 success 或 error。"""
    if extra not in EXTRAS:
        yield {"status": "error", "error": f"Unknown package: {extra}"}
        return
    command = sync_command([*remembered(), extra])
    if command is None:
        yield {
            "status": "error",
            "error": "uv was not found, so nothing can be installed here.",
        }
        return
    yield {"status": "installing", "line": ""}
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    tail: list[str] = []
    assert process.stdout is not None
    async for raw in process.stdout:
        line = raw.decode("utf-8", "replace").rstrip()
        if line:
            tail = (tail + [line])[-5:]
            yield {"status": "installing", "line": line}
    code = await process.wait()
    if code != 0:
        logger.warning(
            f"[extras] installing {extra} failed ({code}): {' | '.join(tail)}"
        )
        yield {"status": "error", "error": "\n".join(tail) or f"uv exited with {code}"}
        return
    if not available(extra):
        yield {
            "status": "error",
            "error": f"{extra} was installed but cannot be imported.",
        }
        return
    remember(extra)
    logger.info(f"[extras] installed {extra}")
    yield {"status": "success"}


def init_extras_route() -> APIRouter:
    router = APIRouter()
    # 同時只裝一個：連按兩下或開兩個分頁，不該跑兩份 uv sync。
    lock = asyncio.Lock()

    @router.get("/api/extras/{name}")
    async def status(name: str, request: Request):
        if not _is_local_request(request):
            return _forbidden()
        if name not in EXTRAS:
            return JSONResponse(
                status_code=404, content={"error": f"Unknown package: {name}"}
            )
        return {
            "name": name,
            "available": await asyncio.to_thread(available, name),
            "installing": lock.locked(),
            "download_mb": EXTRAS[name]["download_mb"],
        }

    @router.post("/api/extras/{name}/install")
    async def install_route(name: str, request: Request):
        """會下載並安裝程式，只接受本機請求。"""
        if not _is_local_request(request):
            return _forbidden()

        async def stream():
            if lock.locked():
                yield (
                    json.dumps({"status": "error", "error": "Already installing."})
                    + "\n"
                )
                return
            async with lock:
                async for event in install(name):
                    yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    return router
