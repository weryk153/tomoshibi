"""一鍵安裝 Ollama：下載官方安裝檔、驗 SHA-256、安裝、啟動。

給不會用終端機的人用。精靈原本在「沒裝 Ollama」時只能給下載連結，使用者得自己
下載、安裝、打開，再回來按重新偵測——每一步都可能卡住。這裡把整串做完，進度用
事件回報給前端。

來源只有 Ollama 在 GitHub 的正式 release，校驗碼取自同一個 release 的
sha256sum.txt。先從 latest 的轉址解析出版本號，再用那個版本號抓安裝檔與校驗碼，
避免兩次請求之間剛好發了新版，檔案和校驗碼對不上。

平台：
- macOS：Ollama-darwin.zip。用 ditto 解壓與複製——Python 的 zipfile 不保留符號
  連結與權限，解出來的 .app 簽章會壞掉。放進 /Applications，不可寫時放
  ~/Applications；已經有一份就沿用，不覆蓋
- Windows x64：OllamaSetup.exe /VERYSILENT。官方安裝腳本（app/ollama.iss）是
  PrivilegesRequired=lowest，不需要管理員，裝在 %LOCALAPPDATA%\\Programs\\Ollama；
  [Run] 是 postinstall 且沒有 skipifsilent，靜默安裝完也會自己啟動
其他平台（Linux、Windows ARM）不支援，前端只顯示下載連結。

直接執行本模組會實際安裝一次，給 CI 在乾淨的機器上驗證用：

    python -m src.open_llm_vtuber.ollama_installer
"""

import asyncio
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import AsyncIterator

import httpx

RELEASES = "https://github.com/ollama/ollama/releases"
API_VERSION_URL = "http://127.0.0.1:11434/api/version"
# macOS 的安裝位置可以覆寫。只給測試用：本機已經裝了 Ollama 時，不能拿使用者的
# /Applications 來試。
APP_DIR_ENV = "TOMOSHIBI_OLLAMA_APP_DIR"
START_TIMEOUT = 90.0
# 替使用者打開 app 之後等這麼久，伺服器還沒起來就改跑內附的 ollama serve。
APP_START_GRACE = 30.0
POLL_INTERVAL = 1.0
PROGRESS_INTERVAL = 0.3
_REDIRECTS = (301, 302, 303, 307, 308)


class InstallError(Exception):
    """訊息會直接顯示給使用者。"""


def asset_name() -> str | None:
    if sys.platform == "darwin":
        return "Ollama-darwin.zip"
    if sys.platform == "win32" and platform.machine().upper() in ("AMD64", "X86_64"):
        return "OllamaSetup.exe"
    return None


def supported() -> bool:
    return asset_name() is not None


def tag_from_location(location: str) -> str:
    m = re.search(r"/releases/download/([^/]+)/", location)
    if not m:
        raise InstallError("Could not find the latest Ollama release.")
    return m.group(1)


def sha256_for(sums: str, asset: str) -> str:
    """從 sha256sum.txt（每行 `<hash>  ./<檔名>`）取出指定檔案的校驗碼。"""
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        name = parts[1].removeprefix("*").removeprefix("./")
        if name == asset and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            return parts[0]
    raise InstallError(f"Ollama didn't publish a checksum for {asset}.")


def mac_app_dir() -> Path:
    override = os.environ.get(APP_DIR_ENV)
    if override:
        return Path(override)
    system = Path("/Applications")
    return system if os.access(system, os.W_OK) else Path.home() / "Applications"


def api_ready(timeout: float = 2.0) -> bool:
    try:
        return httpx.get(API_VERSION_URL, timeout=timeout).status_code == 200
    except httpx.HTTPError:
        return False


def _run(cmd: list[str], failure: str, timeout: float = 600) -> None:
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise InstallError(f"{failure} ({type(e).__name__})") from e
    if result.returncode != 0:
        raise InstallError(f"{failure} (exit {result.returncode})")


def _install_mac(archive: Path, work: Path) -> Path:
    extracted = work / "extracted"
    extracted.mkdir()
    _run(["ditto", "-x", "-k", str(archive), str(extracted)], "Couldn't unpack Ollama.")
    app = extracted / "Ollama.app"
    if not app.is_dir():
        raise InstallError("The Ollama download didn't contain Ollama.app.")
    dest_dir = mac_app_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "Ollama.app"
    if not dest.exists():
        _run(["ditto", str(app), str(dest)], "Couldn't copy Ollama into Applications.")
    return dest


def _install_windows(setup: Path) -> None:
    _run(
        [str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"],
        "The Ollama installer failed.",
        timeout=1800,
    )


def _launch(app: Path | None) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(app or "/Applications/Ollama.app")])
        elif sys.platform == "win32":
            exe = (
                Path(os.environ.get("LOCALAPPDATA", ""))
                / "Programs"
                / "Ollama"
                / "ollama app.exe"
            )
            flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
            subprocess.Popen([str(exe)], creationflags=flags, close_fds=True)
    except OSError as e:
        raise InstallError(
            "Ollama was installed but couldn't be opened. Open the Ollama app, then check again."
        ) from e


def _serve_binary(app: Path | None) -> Path | None:
    """app 內附的 ollama 執行檔。"""
    if sys.platform == "darwin":
        return (
            (app or Path("/Applications/Ollama.app"))
            / "Contents"
            / "Resources"
            / "ollama"
        )
    if sys.platform == "win32":
        return (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "Ollama"
            / "ollama.exe"
        )
    return None


def _start_server(binary: Path) -> None:
    """不靠 app，直接跑 ollama serve。放到自己的 session，Tomoshibi 關掉它也不會跟著停。"""
    kwargs: dict = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen([str(binary), "serve"], **kwargs)
    except OSError as e:
        raise InstallError(
            "Ollama was installed but didn't start. Open the Ollama app, then check again."
        ) from e


async def _wait_until_ready(timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await asyncio.to_thread(api_ready):
            return True
        await asyncio.sleep(POLL_INTERVAL)
    return False


async def install(
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[dict]:
    """依序回報 resolving → downloading（多次）→ verifying → installing →
    starting → success。失敗時丟 InstallError。"""
    asset = asset_name()
    if asset is None:
        raise InstallError("One-click install isn't available on this system.")

    work = Path(tempfile.mkdtemp(prefix="tomoshibi-ollama-"))
    try:
        yield {"status": "resolving"}
        # read 逾時就是「下載卡住」：一分鐘沒有任何資料進來就放棄，而不是永遠轉圈。
        timeout = httpx.Timeout(30.0, read=60.0)
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            latest = await client.get(
                f"{RELEASES}/latest/download/{asset}", follow_redirects=False
            )
            if latest.status_code not in _REDIRECTS:
                raise InstallError("Could not find the latest Ollama release.")
            tag = tag_from_location(latest.headers.get("location", ""))
            sums = await client.get(
                f"{RELEASES}/download/{tag}/sha256sum.txt", follow_redirects=True
            )
            sums.raise_for_status()
            expected = sha256_for(sums.text, asset)

            archive = work / asset
            digest = hashlib.sha256()
            async with client.stream(
                "GET", f"{RELEASES}/download/{tag}/{asset}", follow_redirects=True
            ) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length") or 0)
                done, last = 0, 0.0
                with open(archive, "wb") as f:
                    async for chunk in resp.aiter_bytes(1 << 20):
                        f.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        if now - last >= PROGRESS_INTERVAL:
                            last = now
                            yield {
                                "status": "downloading",
                                "completed": done,
                                "total": total,
                            }
                yield {
                    "status": "downloading",
                    "completed": done,
                    "total": total or done,
                }

        yield {"status": "verifying"}
        if digest.hexdigest() != expected:
            raise InstallError(
                "The download didn't match Ollama's published checksum. Try again."
            )

        yield {"status": "installing"}
        app = None
        if sys.platform == "darwin":
            app = await asyncio.to_thread(_install_mac, archive, work)
        else:
            await asyncio.to_thread(_install_windows, archive)

        yield {"status": "starting"}
        if not await asyncio.to_thread(api_ready):
            await asyncio.to_thread(_launch, app)
            # 乾淨的 macOS 上第一次打開 Ollama.app，等了 90 秒伺服器都沒起來（CI 實測；
            # 本機早就開過 Ollama，所以測不出來）。app 可能停在第一次啟動的畫面，
            # 所以等一小段還沒好，就直接跑內附的 ollama serve，不靠 app。
            if not await _wait_until_ready(APP_START_GRACE):
                binary = _serve_binary(app)
                if binary is None or not binary.exists():
                    raise InstallError(
                        "Ollama was installed but didn't start. Open the Ollama app, then check again."
                    )
                yield {"status": "starting", "fallback": "serve"}
                await asyncio.to_thread(_start_server, binary)
        if not await _wait_until_ready(START_TIMEOUT):
            raise InstallError(
                "Ollama was installed but didn't start. Open the Ollama app, then check again."
            )
        yield {"status": "success", "version": tag}
    finally:
        shutil.rmtree(work, ignore_errors=True)


async def _main() -> int:
    try:
        async for event in install():
            if event["status"] != "downloading":
                print(json.dumps(event), flush=True)
    except InstallError as e:
        print(json.dumps({"status": "error", "error": str(e)}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
