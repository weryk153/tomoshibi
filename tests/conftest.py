"""測試環境的安全網。

裝這個是因為真的出過事：一次重構把設定檔的寫入路徑從 route 模組搬到 conf_editor，
而測試只 patch 了 route 模組的 CONF_PATH。於是測試跑起來，把它自己那份十三行的
假設定檔 dump 進了專案根目錄真正的 conf.yaml——337 個註解只剩 1 個。

測試全綠，什麼警告都沒有。發現的時候是因為 server 起不來。

所以預設就把 conf_editor 的目標指到暫存檔：任何忘了 patch 的測試會寫到那裡，
而不是使用者的設定。需要驗證真實檔案內容的測試自己 monkeypatch 過去就好，
那是明確的動作，不是忘記的後果。
"""

import pytest

from src.open_llm_vtuber import conf_editor


@pytest.fixture(autouse=True)
def _never_touch_the_real_conf(tmp_path, monkeypatch):
    """把 conf_editor 的寫入目標指到本次測試專屬的暫存檔。"""
    sandbox = tmp_path / "conf.yaml"
    if not sandbox.exists():
        sandbox.write_text("system_config: {}\ncharacter_config: {}\n", encoding="utf-8")
    monkeypatch.setattr(conf_editor, "CONF_PATH", str(sandbox))
