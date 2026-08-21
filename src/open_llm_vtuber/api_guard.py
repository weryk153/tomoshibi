"""誰有資格改變伺服器的設定。

所有設定類端點的第一道關卡。這裡沒有密碼，安全性完全建立在「來源可不可信」上，
所以判斷必須保守。

三種可信的來源：

1. **本機自己** —— 而且沒有任何轉發標頭。
2. **使用者自己的 Tailscale 網路** —— tailnet 上的裝置是他已經通過驗證的機器。
   沒有這條，手機或平板透過 Tailscale 連進來就什麼都改不了。
3. **明確打開 allow_remote_config** —— 預設關閉。打開等於信任所有連得到這台
   伺服器的人，只有在完全信任的網路上才該開。

最容易被忽略、也最要命的一條是**反向代理不算本機**：來源 IP 是 127.0.0.1 但帶著
X-Forwarded-For 這類標頭，代表前面有代理，真正的使用者可能在地球任何地方。放行
的話等於任何人都能改你的設定。

這些判斷原本住在 llm_config_route 裡，被另外七個模組 import——一個「LLM 設定」
模組擁有全域的存取守衛沒有道理，而且那樣它一個測試都沒有。契約由
tests/test_api_guard.py 釘住。
"""

from __future__ import annotations

from typing import Any

from ruamel.yaml import YAML
from starlette.responses import JSONResponse

CONF_PATH = "conf.yaml"

# 本機的各種寫法（IPv4、IPv6、以及 IPv6 對映的 IPv4）。
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"}

# 代理會加上這些標頭，而代理會讓遠端使用者的 client.host 看起來是本機。真正從
# 瀏覽器直接連到 localhost 的請求一個都不會帶，所以帶了就代表「被代理過」。
FORWARD_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-real-ip", "forwarded")

# Tailscale 的 CGNAT 範圍：100.64.0.0/10，也就是 100.64.x 到 100.127.x。
_TAILSCALE_FIRST_OCTET = "100."
_TAILSCALE_SECOND_MIN = 64
_TAILSCALE_SECOND_MAX = 127

# Tailscale Serve 會為已驗證的 tailnet 使用者附上這些標頭。
_TAILSCALE_IDENTITY_HEADERS = ("tailscale-user-login", "tailscale-user-name")


def allow_remote_config() -> bool:
    """system_config.allow_remote_config 有沒有打開（預設 False）。

    讀不到設定檔時一律回 False——安全開關的預設值必須是「關」，不能因為檔案有
    問題就變成全開。
    """
    try:
        with open(CONF_PATH, encoding="utf-8") as f:
            data = YAML(typ="safe").load(f) or {}
        return bool((data.get("system_config") or {}).get("allow_remote_config", False))
    except Exception:
        return False


def is_tailscale_ip(ip: str) -> bool:
    """這個位址在不在 Tailscale 的 100.64.0.0/10 範圍內。"""
    if not ip or not ip.startswith(_TAILSCALE_FIRST_OCTET):
        return False
    try:
        second = int(ip.split(".")[1])
    except (ValueError, IndexError):
        return False
    return _TAILSCALE_SECOND_MIN <= second <= _TAILSCALE_SECOND_MAX


def is_tailscale_request(request: Any) -> bool:
    """這個請求是不是來自使用者自己的 tailnet。

    三種形狀都算：直接連到 tailnet IP（真正的 TCP 來源位址，偽造不了）、
    Tailscale Serve 附上的身分標頭、以及 Serve 轉發過來的 tailnet 來源 IP。
    """
    client = getattr(request, "client", None)
    if client is not None and is_tailscale_ip(client.host):
        return True

    headers = request.headers
    if any(headers.get(h) for h in _TAILSCALE_IDENTITY_HEADERS):
        return True

    forwarded = headers.get("x-forwarded-for", "")
    return bool(forwarded) and is_tailscale_ip(forwarded.split(",")[0].strip())


def is_trusted_request(request: Any) -> bool:
    """這個請求可不可以改設定。"""
    if allow_remote_config():
        return True
    if is_tailscale_request(request):
        return True

    client = getattr(request, "client", None)
    if client is None or client.host not in LOCAL_HOSTS:
        return False
    # 本機來源 + 轉發標頭 = 前面有代理，不可信。
    return not any(request.headers.get(h) for h in FORWARD_HEADERS)


def forbidden() -> JSONResponse:
    return JSONResponse(status_code=403, content={"error": "forbidden"})


def mask_key(key: Any) -> str:
    """把 API 金鑰遮成「前幾碼 + ****」，永遠不回傳完整的金鑰。

    短字串只露兩碼——那多半是佔位符，但萬一是真的短金鑰，露一半也太多。
    """
    if key is None:
        return ""
    text = str(key)
    if not text:
        return ""
    visible = text[:4] if len(text) > 6 else text[:2]
    return f"{visible}****"


def make_yaml() -> YAML:
    """round-trip 模式的 YAML 讀寫器：保留註解與結構。

    width 開很大是為了避免長字串被自動換行——那會把使用者手寫的一行拆成好幾行。
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml
