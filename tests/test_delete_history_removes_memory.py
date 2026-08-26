"""刪除一段對話要連它的記憶資料夾一起刪掉。

背景：記憶從角色層搬到對話層之後，一段對話的核心記憶存在
chat_history/<conf_uid>/<history_uid>/core_memory.md ——跟該對話的
chat_history/<conf_uid>/<history_uid>.json 是同名的檔案與資料夾，兄弟關係。

delete_history 原本只 os.remove() 那個 .json，資料夾連同裡面的 core_memory.md
被留在硬碟上，永遠沒有任何活著的連線會再指到那個 history_uid——使用者從歷史
抽屜刪掉一段私密對話，畫面說刪除了，但從那段對話裡萃取出來的每一件私事仍然
以明文留在硬碟上，而且 /api/memory/clear 再也碰不到它（沒有連線會解析出這個
history_uid）。

規格（docs/superpowers/specs/2026-08-22-per-conversation-memory-design.md）的
edge-case 表格寫的是「對話被刪除 → 記憶跟著那個資料夾一起消失（本來就在裡
面）」。這份測試釘住這句話。
"""

import os

from src.open_llm_vtuber import chat_history_manager as chm
from src.open_llm_vtuber import memory_core


def _make_conversation_with_memory(conf_uid: str, content: str = "私密的事") -> str:
    """建一段對話並存一份記憶，回傳它的 history_uid。"""
    history_uid = chm.create_new_history(conf_uid)
    assert history_uid
    memory_core.save_core_memory(conf_uid, history_uid, content)
    return history_uid


def test_deleting_a_conversation_removes_both_json_and_memory_dir(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    conf_uid = "char-a"
    history_uid = _make_conversation_with_memory(conf_uid)

    json_path = chm._get_safe_history_path(conf_uid, history_uid)
    memory_dir = chm._get_safe_history_memory_dir(conf_uid, history_uid)
    assert os.path.isfile(json_path)
    assert os.path.isdir(memory_dir)

    assert chm.delete_history(conf_uid, history_uid) is True

    assert not os.path.exists(json_path)
    assert not os.path.exists(memory_dir)


def test_conversation_with_no_memory_dir_still_deletes_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conf_uid = "char-a"
    history_uid = chm.create_new_history(conf_uid)
    assert history_uid

    json_path = chm._get_safe_history_path(conf_uid, history_uid)
    memory_dir = chm._get_safe_history_memory_dir(conf_uid, history_uid)
    assert os.path.isfile(json_path)
    assert not os.path.exists(memory_dir)

    assert chm.delete_history(conf_uid, history_uid) is True

    assert not os.path.exists(json_path)
    assert not os.path.exists(memory_dir)


def test_deleting_one_conversation_does_not_touch_a_sibling(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conf_uid = "char-a"
    keep_uid = _make_conversation_with_memory(conf_uid, "留著的事")
    delete_uid = _make_conversation_with_memory(conf_uid, "要刪的事")

    assert chm.delete_history(conf_uid, delete_uid) is True

    assert memory_core.load_core_memory(conf_uid, keep_uid) == "留著的事"
    assert os.path.isfile(chm._get_safe_history_path(conf_uid, keep_uid))


def test_hostile_history_uid_cannot_escape_the_character_directory(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    conf_uid = "char-a"
    # A sibling character directory with content that must survive untouched.
    victim_uid = _make_conversation_with_memory("char-b", "受害者的事")

    # A traversal payload as history_uid: after sanitization this collapses to a
    # plain filename (os.path.basename strips the "../" components), so it can
    # only ever resolve to something inside chat_history/char-a/ — never out to
    # chat_history/char-b/. Assert directly that it never reaches outside.
    hostile_uid = "../char-b/conv-1"

    result = chm.delete_history(conf_uid, hostile_uid)
    assert result is False

    # The victim's file and memory survive completely intact.
    assert memory_core.load_core_memory("char-b", victim_uid) == "受害者的事"
    assert os.path.isfile(chm._get_safe_history_path("char-b", victim_uid))
    assert os.path.isdir(chm._get_safe_history_memory_dir("char-b", victim_uid))


def test_hostile_conf_uid_cannot_escape_chat_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "marker.txt").write_text("do not touch", encoding="utf-8")

    result = chm.delete_history("../outside", "conv-1")
    assert result is False
    assert (outside / "marker.txt").read_text(encoding="utf-8") == "do not touch"


def test_get_safe_history_memory_dir_matches_where_memory_core_writes(
    tmp_path, monkeypatch
):
    """core_memory_path 與 _get_safe_history_memory_dir 對同一段對話要指向同一個
    資料夾——這是刪除能不能連記憶一起清掉的前提。"""
    monkeypatch.chdir(tmp_path)
    conf_uid = "char-a"
    history_uid = "conv-1"

    memory_core.save_core_memory(conf_uid, history_uid, "一些內容")
    memory_file = memory_core.core_memory_path(conf_uid, history_uid)
    memory_dir = chm._get_safe_history_memory_dir(conf_uid, history_uid)

    # memory_core.core_memory_path returns a realpath (absolute); the chat
    # history manager's sanitizer returns a plain relative path. Compare
    # resolved paths so the comparison holds regardless of that difference.
    assert os.path.realpath(os.path.dirname(memory_file)) == os.path.realpath(
        memory_dir
    )
