"""角色層的 self_memory.md：她自己的記憶，所有對話共用。

規格：docs/superpowers/specs/2026-09-15-self-memory-design.md。
路徑是 chat_history/<conf_uid>/self_memory.md——不在任何一段對話底下，所以刪對話
不會動到它。conf_uid 是請求可控的，要過 safe_join。
"""

import os

import pytest

from src.open_llm_vtuber.memory_core import (
    SELF_CAP_CHARS,
    clear_self_memory,
    load_self_memory,
    save_self_memory,
    self_memory_path,
)

CONF = "self-store-test"


@pytest.fixture(autouse=True)
def _isolated_chat_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_cap_is_fixed_at_800():
    assert SELF_CAP_CHARS == 800


def test_load_returns_empty_when_nothing_saved():
    assert load_self_memory(CONF) == ""


def test_save_then_load_roundtrip():
    assert save_self_memory(CONF, "  她喜歡咖啡。\n") is True
    assert load_self_memory(CONF) == "她喜歡咖啡。"


def test_path_is_at_character_level_not_under_a_conversation():
    save_self_memory(CONF, "x")
    p = self_memory_path(CONF)
    assert p.endswith(os.path.join("chat_history", CONF, "self_memory.md"))
    assert os.path.isfile(p)


def test_clear_truncates_instead_of_deleting():
    save_self_memory(CONF, "x")
    assert clear_self_memory(CONF) is True
    assert os.path.isfile(self_memory_path(CONF))
    assert load_self_memory(CONF) == ""


def test_clear_on_missing_file_counts_as_cleared():
    assert clear_self_memory(CONF) is True


def test_save_none_means_empty():
    assert save_self_memory(CONF, None) is True
    assert load_self_memory(CONF) == ""


def test_manual_save_over_cap_is_stored_verbatim():
    long = "很" * (SELF_CAP_CHARS + 50)
    assert save_self_memory(CONF, long) is True
    assert load_self_memory(CONF) == long


def test_deleting_a_conversation_keeps_self_memory():
    from src.open_llm_vtuber import chat_history_manager as chm
    from src.open_llm_vtuber.memory_core import save_core_memory

    history_uid = chm.create_new_history(CONF)
    save_core_memory(CONF, history_uid, "對方的私事")
    save_self_memory(CONF, "她喜歡咖啡。")
    assert chm.delete_history(CONF, history_uid) is True
    assert load_self_memory(CONF) == "她喜歡咖啡。"


@pytest.mark.parametrize("evil", ["../other", "..", "a/../../b"])
def test_hostile_conf_uid_fails_soft(evil):
    assert self_memory_path(evil) == ""
    assert load_self_memory(evil) == ""
    assert save_self_memory(evil, "x") is False
    assert clear_self_memory(evil) is False
    assert not os.path.exists(os.path.join("chat_history", "other", "self_memory.md"))
