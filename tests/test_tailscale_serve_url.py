"""Tailscale Serve 的 HTTPS 網址：三種遠端連法裡唯一能用麥克風的那一條。

瀏覽器只在安全來源下開放麥克風，所以 LAN IP 和 Tailscale IP（都是 http）遠端
只能打字。這個函式找的就是那條能講話的網址。

為什麼要有這份測試
------------------
它曾經永遠回 None——`json.loads` 那行的 json 沒有 import，NameError 被外層的
`except Exception: continue` 吞掉，四個 tailscale 路徑全部在同一行炸。設定頁上
那個欄位因此從來沒有出現過網址，就算 Serve 設得完全正確；而且 log 一片乾淨，
看起來只像「大概是沒設好」。

所以這裡不打真的 tailscale，改用假的 serve status 輸出——真機上沒設 Serve 時
回 None，跟壞掉時的回傳一模一樣，那種測試證明不了任何事。
"""

import subprocess
import types

import pytest

from src.open_llm_vtuber import network_route as nr

PORT = 12393
SERVE_JSON = (
    '{"Web":{"mymac.tail1234.ts.net:443":'
    '{"Handlers":{"/":{"Proxy":"http://127.0.0.1:12393"}}}}}'
)


@pytest.fixture
def fake_tailscale(monkeypatch):
    """讓 subprocess.run 回一份指定的 serve status JSON。"""

    def _install(stdout):
        monkeypatch.setattr(
            nr,
            "subprocess",
            types.SimpleNamespace(
                run=lambda *a, **k: subprocess.CompletedProcess(
                    a, 0, stdout=stdout, stderr=""
                )
            ),
        )

    return _install


def test_returns_the_https_url_when_serve_proxies_our_port(fake_tailscale):
    """這正是回歸點：以前這裡永遠是 None。"""
    fake_tailscale(SERVE_JSON)
    assert nr._tailscale_serve_https_url(PORT) == "https://mymac.tail1234.ts.net"


def test_ignores_a_handler_for_a_different_port(fake_tailscale):
    """Serve 可能同時代理別的 app——不能把別人的網址交出去。"""
    fake_tailscale(SERVE_JSON.replace("12393", "9999"))
    assert nr._tailscale_serve_https_url(PORT) is None


def test_no_serve_configured_means_no_url(fake_tailscale):
    fake_tailscale("{}")
    assert nr._tailscale_serve_https_url(PORT) is None


def test_empty_output_is_survivable(fake_tailscale):
    """tailscale 有跑但什麼都沒印。"""
    fake_tailscale("")
    assert nr._tailscale_serve_https_url(PORT) is None


def test_garbage_output_does_not_raise(fake_tailscale):
    """壞掉的 JSON 不能炸——這條在設定頁的讀取路徑上。"""
    fake_tailscale("not json at all")
    assert nr._tailscale_serve_https_url(PORT) is None


def test_no_port_means_no_probe():
    assert nr._tailscale_serve_https_url(None) is None


def test_missing_tailscale_binary_is_quiet(monkeypatch):
    """四個路徑都沒裝 tailscale 是正常情況，不該炸也不該吵。"""

    def boom(*a, **k):
        raise FileNotFoundError("no tailscale here")

    monkeypatch.setattr(nr, "subprocess", types.SimpleNamespace(run=boom))
    assert nr._tailscale_serve_https_url(PORT) is None
