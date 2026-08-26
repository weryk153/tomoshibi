"""記憶屬於一段對話，不是一個角色。

原本是 chat_history/<conf_uid>/core_memory.md，一個角色一份、跨所有對話累積。
她要當直播主之後，那份記憶會跟著進到回答陌生人的那一輪——在直播上講只有你們
兩個知道的事。記憶跟著它形成的那段關係走才對。
"""

import pytest

from src.open_llm_vtuber import memory_core


def test_path_includes_the_conversation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = memory_core.core_memory_path("charA", "conv1")
    assert p.endswith("chat_history/charA/conv1/core_memory.md")


def test_two_conversations_do_not_share_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_core.save_core_memory("charA", "conv1", "只有第一段對話知道的事")
    memory_core.save_core_memory("charA", "conv2", "第二段對話的事")

    assert memory_core.load_core_memory("charA", "conv1") == "只有第一段對話知道的事"
    assert memory_core.load_core_memory("charA", "conv2") == "第二段對話的事"


def test_two_characters_still_do_not_share_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_core.save_core_memory("charA", "conv1", "A 的事")
    memory_core.save_core_memory("charB", "conv1", "B 的事")
    assert memory_core.load_core_memory("charA", "conv1") == "A 的事"


def test_no_conversation_reads_empty(tmp_path, monkeypatch):
    # 連線初始化中 history_uid 還是空字串。這時候要讀到空的，而不是舊路徑。
    monkeypatch.chdir(tmp_path)
    assert memory_core.load_core_memory("charA", "") == ""


def test_no_conversation_writes_nothing(tmp_path, monkeypatch):
    # 退回角色層路徑的話，會變成「有時候寫這裡、有時候寫那裡」——最難查的那種 bug。
    monkeypatch.chdir(tmp_path)
    assert memory_core.save_core_memory("charA", "", "不該被寫出去") is False
    assert not (tmp_path / "chat_history" / "charA" / "core_memory.md").exists()


def test_no_conversation_has_no_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert memory_core.core_memory_path("charA", "") == ""


def test_clear_truncates_only_that_conversation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_core.save_core_memory("charA", "conv1", "會被清掉")
    memory_core.save_core_memory("charA", "conv2", "要留著")

    assert memory_core.clear_core_memory("charA", "conv1") is True

    assert memory_core.load_core_memory("charA", "conv1") == ""
    assert memory_core.load_core_memory("charA", "conv2") == "要留著"
    # house rule：截斷成空檔，不硬刪
    assert (tmp_path / "chat_history" / "charA" / "conv1" / "core_memory.md").is_file()


@pytest.mark.parametrize("evil", ["../escape", "..", "a/../../b"])
def test_a_hostile_conversation_id_cannot_escape(tmp_path, monkeypatch, evil):
    # history_uid 跟 conf_uid 一樣是請求可控的值。
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        memory_core.core_memory_path("charA", evil)


@pytest.mark.parametrize("evil", ["../escape", "..", "a/../../b"])
def test_a_hostile_character_id_cannot_escape(tmp_path, monkeypatch, evil):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        memory_core.core_memory_path(evil, "conv1")
