"""記憶設定的讀取與 conf_uid 驗證——重寫前的特徵測試。

四個「從 conf.yaml 讀一個設定」的函式原本各寫一遍同樣的 try/read/dig/default，
而真正需要被釘住的 _resolve_conf_uid（路徑穿越的防線）一個測試都沒有。

契約：

- 讀不到、壞檔、缺鍵，一律回程式端的預設值——設定頁不能因為 conf.yaml 有問題
  就整個打不開。
- 讀出來的值會被夾進合法範圍，UI 永遠不會顯示一個超界的數字。
- conf_uid 是使用者送來的：不在已知集合裡就拒絕，帶路徑符號的直接擋。
"""

import pytest

from src.open_llm_vtuber import memory_core
from src.open_llm_vtuber import memory_route as mr


CONF = """\
character_config:
  conf_uid: aoi
  long_term_memory_enabled: False
  core_memory_max_chars: 3000
  memory_consolidation_interval: 3
"""


@pytest.fixture()
def conf(monkeypatch):
    """把 conf.yaml 的「內容」換掉，不碰檔案系統。

    read_yaml 有路徑安全檢查，只讀得到專案目錄底下的檔案——測試不能把 conf.yaml
    丟到 tmp_path 再指過去（那會走進例外處理，量到的是 fallback 而不是讀取邏輯）。
    所以換掉的是解析結果這個接縫。
    """
    from ruamel.yaml import YAML

    def _use(text: str):
        def fake_read_yaml(_path):
            return YAML(typ="safe").load(text)

        monkeypatch.setattr(mr, "read_yaml", fake_read_yaml)

    return _use


# --- 讀設定 ------------------------------------------------------------------


def test_reads_the_saved_values(conf):
    conf(CONF)

    assert mr._base_conf_uid() == "aoi"
    assert mr._memory_enabled_from_conf() is False
    assert mr._cap_from_conf() == 3000
    assert mr._interval_from_conf() == 3


def test_missing_keys_fall_back_to_code_defaults(conf):
    conf("character_config:\n  conf_uid: aoi\n")

    # 記憶預設是開的（跟 Pydantic 的預設一致）。
    assert mr._memory_enabled_from_conf() is True
    assert mr._cap_from_conf() == memory_core.CAP_CHARS
    assert mr._interval_from_conf() == memory_core.CONSOLIDATE_INTERVAL_DEFAULT


def test_broken_conf_does_not_break_the_panel(monkeypatch):
    def explode(_path):
        raise ValueError("conf.yaml unreadable")

    monkeypatch.setattr(mr, "read_yaml", explode)

    assert mr._memory_enabled_from_conf() is True
    assert mr._cap_from_conf() == memory_core.CAP_CHARS
    assert mr._interval_from_conf() == memory_core.CONSOLIDATE_INTERVAL_DEFAULT
    assert mr._base_conf_uid() is None


def test_out_of_range_values_are_clamped_on_read(conf):
    # UI 顯示的數字永遠要在合法範圍內，就算 conf.yaml 被手改成離譜的值。
    conf(
        "character_config:\n"
        "  conf_uid: aoi\n"
        "  core_memory_max_chars: 999999\n"
        "  memory_consolidation_interval: 4\n"
    )

    assert mr._cap_from_conf() == memory_core.CAP_MAX
    assert mr._interval_from_conf() == memory_core.CONSOLIDATE_INTERVAL_DEFAULT


# --- conf_uid 驗證 -----------------------------------------------------------


def test_blank_falls_back_to_the_base_character(conf, monkeypatch):
    conf(CONF)

    assert mr._resolve_conf_uid(None) == ("aoi", None)
    assert mr._resolve_conf_uid("   ") == ("aoi", None)


def test_known_uid_is_accepted(conf, monkeypatch):
    conf(CONF)
    monkeypatch.setattr(mr, "_existing_conf_uids", lambda: {"aoi", "frieren"})

    assert mr._resolve_conf_uid("frieren") == ("frieren", None)


def test_unknown_uid_is_rejected(conf, monkeypatch):
    conf(CONF)
    monkeypatch.setattr(mr, "_existing_conf_uids", lambda: {"aoi"})

    uid, err = mr._resolve_conf_uid("someone-else")

    assert uid is None
    assert err


@pytest.mark.parametrize(
    "evil", ["../secrets", "a/b", "a\\b", "..", "../../etc/passwd"]
)
def test_path_traversal_is_rejected_before_the_known_set_check(conf, monkeypatch, evil):
    # 這條是安全防線：路徑符號在比對已知集合「之前」就要擋掉。
    conf(CONF)
    monkeypatch.setattr(
        mr,
        "_existing_conf_uids",
        lambda: {evil},  # 就算它在集合裡也要擋
    )

    uid, err = mr._resolve_conf_uid(evil)

    assert uid is None
    assert err


def test_no_base_and_no_supplied_is_an_error(conf):
    conf("character_config: {}\n")

    uid, err = mr._resolve_conf_uid(None)

    assert uid is None
    assert err
