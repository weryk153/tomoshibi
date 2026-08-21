"""遠端存取：這台伺服器現在能被誰連到，以及要不要開放給其他裝置。

三種連進來的方式，對使用者的意義完全不同：

- **同一個 Wi-Fi**（LAN 位址）：最直覺，但只有在伺服器綁到 0.0.0.0 時才通。
- **Tailscale IP**：在任何地方都連得到，前提是兩端都登入同一個 tailnet。
- **Tailscale Serve 的 HTTPS 網址**：唯一能用麥克風的遠端方式。瀏覽器只在
  安全來源下開放麥克風，純 IP 的 http 可以打字但不能講話。

綁定位址是整個設定頁最敏感的開關。改成 0.0.0.0 之後，同一個網路上的任何人都
連得到，而這裡沒有密碼。所以寫入端點跟其他設定走同一道守衛，回應一定帶著
「要重啟才生效」——不能讓人以為按下去就安全地生效了。

這些原本住在 character_route 裡。網路設定跟角色管理沒有關係，而且那樣它就不會
有寫入能力：早期的設定頁只能顯示現況，要真的開放必須手動編輯 conf.yaml。
"""

from __future__ import annotations

import asyncio
import os
import re
import socket
import subprocess
from typing import Optional

from fastapi import APIRouter, Request
from loguru import logger
from starlette.responses import JSONResponse

from .api_guard import (
    forbidden as _forbidden,
    is_tailscale_ip as _is_cgnat,
    is_trusted_request as _is_local_request,
)
from .conf_editor import (
    CONF_PATH,
    read_conf_lines,
    system_config_extent,
    upsert_leaf,
    write_conf,
)
from .config_manager.utils import read_yaml

# 綁到這些位址代表「只有這台機器連得到」。
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
# 開放給其他裝置時綁的位址：所有介面。
OPEN_HOST = "0.0.0.0"


def is_localhost_only(host: str) -> bool:
    """這個綁定位址是不是只有本機連得到。"""
    return str(host).strip() in LOOPBACK_HOSTS


def current_host() -> str:
    """conf.yaml 裡設的綁定位址；讀不到就當成 loopback（最保守的假設）。"""
    try:
        conf = read_yaml(CONF_PATH) or {}
        return str((conf.get("system_config") or {}).get("host", "")).strip() or "127.0.0.1"
    except Exception:
        return "127.0.0.1"


def _server_bound_localhost_only() -> bool:
    """伺服器是不是只聽 loopback。

    是的話，底下算出來的 LAN 與 Tailscale IP 網址其實連不通——UI 要據此顯示
    引導，而不是列出一串按了沒反應的網址。（Tailscale Serve 不受影響，它是從
    loopback 代理進來的。）
    """
    return is_localhost_only(current_host())


def write_host(allow_other_devices: bool) -> None:
    """改寫綁定位址。開放＝0.0.0.0，關閉＝127.0.0.1。

    沒有那一行就補上——手寫的 conf.yaml 常常沒有 host，不該因此存不了。
    """
    lines = read_conf_lines()
    start, end = system_config_extent(lines)
    host = OPEN_HOST if allow_other_devices else "127.0.0.1"
    upsert_leaf(lines, start, end, "host", f"'{host}'")
    write_conf(lines)



def _lan_ip() -> Optional[str]:
    """Best-effort primary LAN IPv4 — the address other devices on the same
    network would use. Standard UDP-connect trick: no packet is sent, it just
    makes the OS pick the outbound interface."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        return ip if ip and not ip.startswith("127.") else None
    except Exception:
        return None
    finally:
        s.close()


def _tailscale_ip() -> Optional[str]:
    """Best-effort Tailscale IPv4 (100.64.0.0/10). Tries the `tailscale` CLI in
    its usual locations, then scans local addresses for the CGNAT range."""
    for exe in (
        "tailscale",
        "/usr/local/bin/tailscale",
        "/opt/homebrew/bin/tailscale",
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    ):
        try:
            out = subprocess.run(
                [exe, "ip", "-4"], capture_output=True, text=True, timeout=3
            )
            lines = (out.stdout or "").strip().splitlines()
            ip = lines[0].strip() if lines else ""
            if _is_cgnat(ip):
                return ip
        except Exception:
            continue
    try:
        for res in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = res[4][0]
            if _is_cgnat(ip):
                return ip
    except Exception:
        pass
    return None


def _serve_host_to_url(host: str) -> str:
    """把 serve status 的 "host:port" 接成網址，443 不寫出來。

    Serve 預設就掛在 443，把它原樣留著會讓設定頁的複製按鈕和 QR code 裡都帶著
    一串 :443——能用，但使用者手抄或唸給別人時多一個沒必要的東西。掛在別的埠
    （tailscale serve --https=8443）時那個埠是必要資訊，要留著。
    """
    cleaned = host.strip()
    if cleaned.endswith(":443"):
        cleaned = cleaned[: -len(":443")]
    return f"https://{cleaned}"


def _tailscale_serve_https_url(port: Optional[int]) -> Optional[str]:
    """If Tailscale Serve proxies HTTPS to our port, return that https:// URL —
    the mic-capable one. Matches the serve handler whose proxy target port equals
    our server port, so we never hand back a URL pointing at a different app."""
    if not port:
        return None
    for exe in (
        "tailscale",
        "/usr/local/bin/tailscale",
        "/opt/homebrew/bin/tailscale",
        "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
    ):
        try:
            out = subprocess.run(
                [exe, "serve", "status", "--json"],
                capture_output=True, text=True, timeout=3,
            )
            data = json.loads(out.stdout or "{}")
            web = data.get("Web") or {}
            for host, cfg in web.items():
                for _path, h in (cfg.get("Handlers") or {}).items():
                    proxy = (h.get("Proxy") or "").rstrip("/")
                    if proxy.endswith(f":{port}"):
                        return _serve_host_to_url(host)
            return None  # tailscale ran but nothing maps to our port
        except Exception:
            continue
    return None


def _collect_network_urls(request: Request) -> dict:
    """Reachable URLs other devices can use to open this companion: the LAN URL
    (same Wi-Fi), the Tailscale URL (anywhere), and — if Tailscale Serve is
    proxying HTTPS to this port — the secure HTTPS URL the microphone needs."""
    scheme = request.url.scheme or "http"
    port = request.url.port
    default_port = 443 if scheme == "https" else 80

    def make_url(ip: str) -> str:
        if port and port != default_port:
            return f"{scheme}://{ip}:{port}"
        return f"{scheme}://{ip}"

    urls = []
    lan = _lan_ip()
    if lan:
        urls.append({"type": "lan", "ip": lan, "url": make_url(lan)})
    ts = _tailscale_ip()
    if ts:
        urls.append({"type": "tailscale", "ip": ts, "url": make_url(ts)})

    https_url = _tailscale_serve_https_url(port) if scheme != "https" else None

    return {
        "urls": urls,
        "port": port,
        "scheme": scheme,
        # The secure URL the microphone needs, auto-detected from Tailscale Serve
        # (null when Serve isn't proxying HTTPS to this port).
        "https_url": https_url,
        # True when the server only listens on loopback — the LAN/Tailscale-IP
        # URLs above won't connect, so the UI shows setup guidance instead.
        "localhost_only": _server_bound_localhost_only(),
        # Microphone capture needs a secure context (HTTPS) on a remote host;
        # plain-IP http works for text but not the mic. Tailscale Serve = HTTPS.
        "mic_needs_https": scheme != "https",
    }


def init_network_route() -> APIRouter:
    """遠端存取的端點。"""
    router = APIRouter()

    @router.get("/api/network-info")
    async def network_info(request: Request):
        # 刻意不限本機：已經連到這台伺服器的裝置，本來就有資格知道其他可用的
        # 網址（例如要把網址給平板）。回傳的只有非機密的 LAN／Tailscale 位址。
        info = await asyncio.to_thread(_collect_network_urls, request)
        return JSONResponse(info)

    @router.post("/api/network/host")
    async def set_host(request: Request):
        """開放或關閉其他裝置的連線。

        這是敏感操作，所以跟其他設定端點一樣要通過信任來源的檢查。
        """
        if not _is_local_request(request):
            return _forbidden()

        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict) or "allow_other_devices" not in body:
            return JSONResponse(
                status_code=400,
                content={"ok": False, "error": "Missing 'allow_other_devices' boolean."},
            )

        allow = bool(body["allow_other_devices"])
        try:
            await asyncio.to_thread(write_host, allow)
        except Exception as e:
            logger.error(f"[network] host write failed: {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": "Could not write config file."},
            )

        logger.info(f"[network] host set to {'0.0.0.0' if allow else '127.0.0.1'}")
        return JSONResponse(
            {
                "ok": True,
                "allow_other_devices": allow,
                "host": OPEN_HOST if allow else "127.0.0.1",
                # 綁定位址在啟動時就決定了，改完一定要重啟。
                "restart_required": True,
            }
        )

    return router
