"""記憶開關的欄位在 conf.yaml 不存在時，寫入要能自己補上。

外科手術式寫入原本要求 leaf 必須先存在（由人手動加進 conf.yaml）。但這個
設定在 UI 上開得出來、也有程式預設值，使用者從沒手動加過那一行——結果一動
就必爆（當時是記憶上限，KeyError: 'core_memory_max_chars leaf not found'）。

UI 開得出來的設定就該存得下去。缺欄位時插入到 character_config 區塊尾端，
其餘既存欄位、註解、縮排一律不動。
"""

import re

import pytest

from src.open_llm_vtuber import conf_editor as ce
from src.open_llm_vtuber import memory_route as mr

CONF_WITHOUT_LEAVES = """\
system_config:
  host: '127.0.0.1'
  port: 12393

character_config:
  conf_name: 'aoi'   # 角色名
  conf_uid: 'aoi'

  # 一段註解
  persona_prompt: |
    你是詠梨。

  agent_config:
    conversation_agent_choice: 'character_engine_agent'
"""

CONF_WITH_LEAVES = """\
character_config:
  conf_name: 'aoi'
  long_term_memory_enabled: false   # 保留這個註解
"""


@pytest.fixture
def conf(tmp_path, monkeypatch):
    """把 CONF_PATH 指到暫存檔，避免動到真的 conf.yaml。"""

    path = tmp_path / "conf.yaml"

    def _use(text: str):
        path.write_text(text, encoding="utf-8")
        # 兩個都要指過去：memory_route 是 `from .conf_editor import CONF_PATH`，
        # 綁的是當下的值，改 conf_editor 的不會連動。
        monkeypatch.setattr(mr, "CONF_PATH", str(path))
        monkeypatch.setattr(ce, "CONF_PATH", str(path))
        return path

    return _use


def test_enabled_toggle_inserts_when_missing(conf):
    path = conf(CONF_WITHOUT_LEAVES)
    assert mr._write_memory_enabled(True) is True
    assert re.search(
        r"^  long_term_memory_enabled: True$", path.read_text(encoding="utf-8"), re.M
    )


def test_insert_lands_inside_character_config(conf):
    """插入的欄位必須是 character_config 的直接子項，不能掉到別的區塊。"""
    path = conf(CONF_WITHOUT_LEAVES)
    mr._write_memory_enabled(True)
    lines = path.read_text(encoding="utf-8").splitlines()
    cc = next(i for i, ln in enumerate(lines) if ln.startswith("character_config:"))
    leaf = next(i for i, ln in enumerate(lines) if "long_term_memory_enabled" in ln)
    # 在 character_config 之後，且在下一個頂層區塊之前
    following_top_level = [
        i
        for i, ln in enumerate(lines)
        if i > cc and ln.strip() and not ln.startswith((" ", "\t", "#"))
    ]
    assert leaf > cc
    assert all(leaf < i for i in following_top_level)


def test_insert_preserves_existing_content(conf):
    path = conf(CONF_WITHOUT_LEAVES)
    mr._write_memory_enabled(True)
    text = path.read_text(encoding="utf-8")
    assert "# 一段註解" in text
    assert "conf_name: 'aoi'   # 角色名" in text
    assert "conversation_agent_choice: 'character_engine_agent'" in text
    assert "你是詠梨。" in text


def test_existing_leaf_is_rewritten_not_duplicated(conf):
    path = conf(CONF_WITH_LEAVES)
    mr._write_memory_enabled(True)
    text = path.read_text(encoding="utf-8")
    assert text.count("long_term_memory_enabled") == 1
    assert "long_term_memory_enabled: True   # 保留這個註解" in text


def test_inserted_conf_still_parses_as_yaml(conf):
    path = conf(CONF_WITHOUT_LEAVES)
    mr._write_memory_enabled(False)

    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(path.read_text(encoding="utf-8"))
    cc = data["character_config"]
    assert cc["long_term_memory_enabled"] is False
    # 既有內容沒被破壞
    assert cc["conf_uid"] == "aoi"
    assert data["system_config"]["port"] == 12393
