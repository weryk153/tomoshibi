"""GET /api/network-info 回報的 Tailscale Serve HTTPS 網址。

`tailscale serve status --json` 的 Web 鍵是 "host:port"，而 Serve 預設就掛在
443。把它原樣接成網址會得到 https://name.ts.net:443——能用，但那串 :443 會一路
出現在設定頁的複製按鈕和 QR code 裡，使用者手抄或唸給別人時多一個沒必要的
東西。預設埠不該寫出來。
"""

from src.open_llm_vtuber.network_route import _serve_host_to_url


def test_drops_the_default_https_port():
    assert _serve_host_to_url("kurenmacbook-pro.tailf70fde.ts.net:443") == (
        "https://kurenmacbook-pro.tailf70fde.ts.net"
    )


def test_keeps_a_non_default_port():
    # Serve 可以掛在別的埠（tailscale serve --https=8443），那時候埠是必要資訊。
    assert _serve_host_to_url("host.ts.net:8443") == "https://host.ts.net:8443"


def test_host_without_port_is_left_alone():
    assert _serve_host_to_url("host.ts.net") == "https://host.ts.net"


def test_strips_surrounding_whitespace():
    assert _serve_host_to_url("  host.ts.net:443  ") == "https://host.ts.net"
