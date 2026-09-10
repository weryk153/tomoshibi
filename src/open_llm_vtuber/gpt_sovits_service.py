"""GPT-SoVITS 的 API 行程：跟著 Tomoshibi 的伺服器一起開、一起關。

只管設定精靈裝的那一份（gpt_sovits_installer）。使用者自己架的 GPT-SoVITS 不碰：
啟動前先看 9880 有沒有人在回應，有就沿用，不會多開一個去搶埠。

伺服器被強制結束時，這個行程可能留下來。下次啟動看到 9880 有回應就直接沿用，
不會開第二個。
"""

import asyncio
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import httpx
import psutil
from loguru import logger

from . import gpt_sovits_installer as installer
from .conf_editor import CONF_PATH
from .config_manager.utils import read_yaml

READY_URL = f"http://{installer.API_HOST}:{installer.API_PORT}/docs"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

_proc: subprocess.Popen | None = None


def api_ready(timeout: float = 2.0) -> bool:
    try:
        return httpx.get(READY_URL, timeout=timeout).status_code == 200
    except httpx.HTTPError:
        return False


def start() -> bool:
    """開 API。已經有人在 9880 回應（我們先前開的、或使用者自己的）就不再開。"""
    global _proc
    if _proc is not None and _proc.poll() is None:
        return True
    if api_ready():
        return True
    info = installer.read_marker()
    if info is None:
        return False

    cmd = [
        info["python"],
        *info.get("args", []),
        "api_v2.py",
        "-a",
        installer.API_HOST,
        "-p",
        str(installer.API_PORT),
        "-c",
        str(installer.tts_infer_path()),
    ]
    log_path = installer.install_root() / "api.log"
    try:
        with open(log_path, "ab") as log:
            _proc = subprocess.Popen(
                cmd,
                cwd=info["app_dir"],
                env=installer.clean_env(**info.get("env", {})),
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                **installer.no_window(),
            )
    except OSError as e:
        logger.warning(f"[gpt-sovits] couldn't start the API: {type(e).__name__}: {e}")
        return False
    logger.info(f"[gpt-sovits] starting the API (log: {log_path})")
    return True


async def wait_ready(timeout: float) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if await asyncio.to_thread(api_ready):
            return True
        if _proc is not None and _proc.poll() is not None:
            logger.warning(f"[gpt-sovits] the API exited with code {_proc.returncode}")
            return False
        await asyncio.sleep(1.0)
    return False


def stop() -> None:
    """只停我們自己開的那一個，連同它開出來的子行程。"""
    global _proc
    proc, _proc = _proc, None
    if proc is None or proc.poll() is not None:
        return
    try:
        children = psutil.Process(proc.pid).children(recursive=True)
    except psutil.Error:
        children = []
    for child in children:
        try:
            child.terminate()
        except psutil.Error:
            pass
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    _, alive = psutil.wait_procs(children, timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass


def wanted_by_config() -> bool:
    """有沒有哪一份角色設定用的是本機 9880 的 GPT-SoVITS。"""
    for path in [Path(CONF_PATH), *sorted(Path("characters").glob("*.yaml"))]:
        try:
            data = read_yaml(str(path)) or {}
        except Exception:
            continue
        tts = (data.get("character_config") or {}).get("tts_config") or {}
        if tts.get("tts_model") != "gpt_sovits_tts":
            continue
        url = urlparse(str((tts.get("gpt_sovits_tts") or {}).get("api_url") or ""))
        if url.hostname in _LOCAL_HOSTS and url.port == installer.API_PORT:
            return True
    return False


async def autostart() -> None:
    """伺服器啟動時呼叫。裝好了、而且設定真的要用，才開。"""
    if installer.read_marker() is None or not wanted_by_config():
        return
    await asyncio.to_thread(start)
