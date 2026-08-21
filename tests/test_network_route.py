"""遠端存取：讀得到現況，也改得動綁定位址。

原本這條路是唯讀的——設定頁只能顯示「其他裝置連不連得到」，要真的打開必須手動
編輯 conf.yaml 的 system_config.host。UI 開得出來的東西就該存得下去。

安全上這是整個設定頁裡最敏感的一個開關：綁到 0.0.0.0 之後，同一個網路上的任何
人都連得到這台伺服器，而這裡沒有密碼。所以：

- 只接受可信來源（跟其他設定端點同一道守衛）。
- 回應一定帶警語與「要重啟才生效」，不能讓使用者以為按下去就安全地生效了。
"""

import pytest

from src.open_llm_vtuber import conf_editor as ce
from src.open_llm_vtuber import network_route as nr


CONF = """\
system_config:
  host: '127.0.0.1'  # 只聽本機
  port: 12393
"""


@pytest.fixture()
def conf(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(nr, "CONF_PATH", str(path))
    return path


def test_loopback_is_recognised_as_localhost_only():
    for host in ("127.0.0.1", "localhost", "::1"):
        assert nr.is_localhost_only(host) is True


def test_a_wildcard_bind_is_not_localhost_only():
    for host in ("0.0.0.0", "::", "192.168.1.10"):
        assert nr.is_localhost_only(host) is False


def test_opening_up_writes_the_wildcard_address(conf):
    nr.write_host(allow_other_devices=True)

    assert "host: '0.0.0.0'" in conf.read_text(encoding="utf-8")


def test_closing_down_returns_to_loopback(conf):
    nr.write_host(allow_other_devices=True)
    nr.write_host(allow_other_devices=False)

    assert "host: '127.0.0.1'" in conf.read_text(encoding="utf-8")


def test_the_users_comment_survives(conf):
    nr.write_host(allow_other_devices=True)

    assert "# 只聽本機" in conf.read_text(encoding="utf-8")


def test_the_key_is_created_when_absent(tmp_path, monkeypatch):
    # 手寫的 conf.yaml 可能根本沒有 host 那一行——不該因此存不了。
    path = tmp_path / "conf.yaml"
    path.write_text("system_config:\n  port: 12393\n", encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(nr, "CONF_PATH", str(path))

    nr.write_host(allow_other_devices=True)

    assert "host: '0.0.0.0'" in path.read_text(encoding="utf-8")
