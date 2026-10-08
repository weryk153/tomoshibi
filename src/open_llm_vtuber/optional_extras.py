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
from typing import Any, AsyncIterator, Callable, Optional

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
    # 套件要的其他東西（faster-whisper 的語音模型）也在這裡下載、回報進度。以前是
    # 重新載入時後端默默下載 1.6GB，畫面一直「載入中」，看起來像卡住。
    prepare = PREPARE.get(extra)
    if prepare is not None:
        try:
            async for event in prepare():
                yield event
        except Exception as e:  # noqa: BLE001 — 套件已經裝好了，再按一次只補模型
            logger.warning(
                f"[extras] preparing {extra} failed: {type(e).__name__}: {e}"
            )
            yield {
                "status": "error",
                "error": f"Downloading the speech model failed: {e}",
            }
            return
    yield {"status": "success"}


def folder_size(path: str) -> int:
    """資料夾裡實際的檔案大小（不算連結；下載中的 .incomplete 也算）。"""
    total = 0
    for folder, _, files in os.walk(path):
        for name in files:
            file = os.path.join(folder, name)
            if not os.path.islink(file):
                try:
                    total += os.path.getsize(file)
                except OSError:
                    pass
    return total


def whisper_model_settings() -> tuple[str, str]:
    """設定裡的 faster-whisper 模型與下載資料夾（conf.yaml）。"""
    from .config_manager.utils import read_yaml

    try:
        block = read_yaml("conf.yaml")["character_config"]["asr_config"][
            "faster_whisper"
        ]
    except Exception:  # noqa: BLE001 — 讀不到就用預設
        block = {}
    return (
        str(block.get("model_path") or "large-v3-turbo"),
        str(block.get("download_root") or "models/whisper"),
    )


# faster_whisper.utils.download_model 下載的檔案（跟它的 allow_patterns 一致）。
_WHISPER_FILES = (
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
)


def _repo_size(repo: str) -> int:
    import fnmatch

    from huggingface_hub import HfApi

    try:
        info = HfApi().model_info(repo, files_metadata=True)
    except Exception:  # noqa: BLE001 — 問不到總大小就只顯示已下載多少
        return 0
    return sum(
        sibling.size or 0
        for sibling in info.siblings or ()
        if any(
            fnmatch.fnmatch(sibling.rfilename, pattern) for pattern in _WHISPER_FILES
        )
    )


async def _download_whisper_model() -> AsyncIterator[dict[str, Any]]:
    """下載設定裡的 faster-whisper 模型，每半秒回報一次已下載多少。"""
    model, root = whisper_model_settings()
    if os.path.exists(model):  # 本機路徑：不用下載
        return
    import huggingface_hub.constants as hub
    from faster_whisper.utils import _MODELS, download_model

    repo = _MODELS.get(model, model)
    # 問總大小要好幾秒：先讓畫面換成「準備下載語音模型」，不要停在上一行安裝訊息。
    yield {"status": "model", "completed": 0, "total": 0}
    total = await asyncio.to_thread(_repo_size, repo)
    folder = os.path.join(root, "models--" + repo.replace("/", "--"))
    # hf-xet 下載完才一次寫進資料夾，算不出進度；改走一般 HTTP，邊下邊寫。
    hub.HF_HUB_DISABLE_XET = True
    task = asyncio.ensure_future(
        asyncio.to_thread(download_model, model, cache_dir=root)
    )
    while not task.done():
        yield {"status": "model", "completed": folder_size(folder), "total": total}
        await asyncio.wait({task}, timeout=0.5)
    task.result()
    done = folder_size(folder)
    yield {"status": "model", "completed": max(done, total), "total": max(done, total)}


# 裝好套件之後還要準備的東西（名字 → 回報進度的 async generator）。
PREPARE: dict[str, Callable[[], AsyncIterator[dict[str, Any]]]] = {
    "faster_whisper": _download_whisper_model,
}


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
