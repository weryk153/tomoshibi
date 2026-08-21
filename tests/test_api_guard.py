"""誰可以改設定——存取守衛的契約測試。

這段程式決定「這個請求有沒有資格改變伺服器設定」。它原本住在 llm_config_route
裡，被其他七個模組 import，卻沒有一個測試。

信任的三種來源：

1. 本機自己（127.0.0.1 / ::1），而且沒有任何代理標頭。
2. 使用者自己的 Tailscale 網路上的裝置——那是他已通過驗證的機器。
3. system_config.allow_remote_config 明確打開（預設關閉，代表信任所有連得到的人）。

最重要的一條是**反向代理不算本機**：一個 localhost 的來源 IP 加上轉發標頭，
代表前面有代理，真正的使用者可能在任何地方。放行的話等於任何人都能改設定。
"""

from types import SimpleNamespace

import pytest

from src.open_llm_vtuber import api_guard as g


def _request(host="127.0.0.1", headers=None):
    return SimpleNamespace(
        client=SimpleNamespace(host=host) if host else None,
        headers=headers or {},
    )


@pytest.fixture(autouse=True)
def _no_remote_opt_in(monkeypatch):
    """預設關閉遠端設定，個別測試要打開再自己 patch。"""
    monkeypatch.setattr(g, "allow_remote_config", lambda: False)


# --- 本機 --------------------------------------------------------------------


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_localhost_is_trusted(host):
    assert g.is_trusted_request(_request(host)) is True


def test_a_remote_address_is_not_trusted():
    assert g.is_trusted_request(_request("203.0.113.9")) is False


def test_a_request_without_a_client_is_not_trusted():
    assert g.is_trusted_request(_request(None)) is False


@pytest.mark.parametrize(
    "header", ["x-forwarded-for", "x-real-ip", "forwarded"]
)
def test_localhost_behind_a_proxy_is_not_trusted(header):
    # 這是最重要的一條：來源是 localhost 但帶著轉發標頭，代表前面有反向代理，
    # 真正的使用者可能在任何地方。放行等於誰都能改設定。
    assert g.is_trusted_request(_request("127.0.0.1", {header: "203.0.113.9"})) is False


# --- Tailscale ---------------------------------------------------------------


@pytest.mark.parametrize("ip", ["100.64.0.1", "100.100.5.5", "100.127.255.254"])
def test_tailscale_range_is_recognised(ip):
    assert g.is_tailscale_ip(ip) is True


@pytest.mark.parametrize("ip", ["100.63.0.1", "100.128.0.1", "10.0.0.1", "", "100.x.1.1"])
def test_addresses_outside_the_range_are_not_tailscale(ip):
    assert g.is_tailscale_ip(ip) is False


def test_a_direct_tailnet_dial_is_trusted():
    # 真正的 TCP 來源位址是偽造不了的。
    assert g.is_trusted_request(_request("100.101.102.103")) is True


def test_tailscale_serve_identity_headers_are_trusted():
    request = _request("127.0.0.1", {"tailscale-user-login": "me@example.com"})

    assert g.is_trusted_request(request) is True


def test_tailscale_serve_forwarded_ip_is_trusted():
    request = _request("127.0.0.1", {"x-forwarded-for": "100.64.1.2, 10.0.0.1"})

    assert g.is_trusted_request(request) is True


# --- 明確開放 ----------------------------------------------------------------


def test_opt_in_trusts_everyone(monkeypatch):
    monkeypatch.setattr(g, "allow_remote_config", lambda: True)

    assert g.is_trusted_request(_request("203.0.113.9")) is True


# --- 遮罩 --------------------------------------------------------------------


def test_keys_are_masked_never_shown_whole():
    assert g.mask_key("sk-1234567890abcdef") == "sk-1****"
    assert g.mask_key("short") == "sh****"
    assert g.mask_key("") == ""
    assert g.mask_key(None) == ""


def test_forbidden_is_a_403():
    assert g.forbidden().status_code == 403
