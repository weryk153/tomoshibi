"""既有的角色層記憶要搬到該角色 active 的那段對話。

不搬的話,下次連上她就失憶了——檔案還在硬碟上,但沒有任何程式碼會去讀它。
使用者失去的是無法重建的東西:她記得你的那些事,不是快取。
"""

from src.open_llm_vtuber import memory_migration


def _old(tmp_path, conf_uid, text):
    d = tmp_path / "chat_history" / conf_uid
    d.mkdir(parents=True, exist_ok=True)
    (d / "core_memory.md").write_text(text, encoding="utf-8")


def test_moves_memory_into_the_active_conversation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _old(tmp_path, "charA", "她記得的事")
    monkeypatch.setattr(memory_migration, "get_active_history_uid", lambda c: "conv1")

    assert memory_migration.migrate_character_memories() == ["charA"]

    moved = tmp_path / "chat_history" / "charA" / "conv1" / "core_memory.md"
    assert moved.read_text(encoding="utf-8") == "她記得的事"


def test_keeps_the_old_file_under_a_new_name(tmp_path, monkeypatch):
    # 搬錯了還救得回來。這種一次性搬移出錯時,使用者失去的東西無法重建。
    monkeypatch.chdir(tmp_path)
    _old(tmp_path, "charA", "她記得的事")
    monkeypatch.setattr(memory_migration, "get_active_history_uid", lambda c: "conv1")

    memory_migration.migrate_character_memories()

    assert not (tmp_path / "chat_history" / "charA" / "core_memory.md").exists()
    kept = tmp_path / "chat_history" / "charA" / "core_memory.md.pre-split"
    assert kept.read_text(encoding="utf-8") == "她記得的事"


def test_skips_a_character_with_no_active_conversation(tmp_path, monkeypatch):
    # 憑空建立一段對話,會產生使用者從來沒開過的對話,而且記憶被塞在裡面。
    monkeypatch.chdir(tmp_path)
    _old(tmp_path, "charA", "她記得的事")
    monkeypatch.setattr(memory_migration, "get_active_history_uid", lambda c: None)

    assert memory_migration.migrate_character_memories() == []
    assert (tmp_path / "chat_history" / "charA" / "core_memory.md").exists()


def test_does_not_overwrite_an_existing_conversation_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _old(tmp_path, "charA", "舊的")
    dest = tmp_path / "chat_history" / "charA" / "conv1"
    dest.mkdir(parents=True)
    (dest / "core_memory.md").write_text("已經有的", encoding="utf-8")
    monkeypatch.setattr(memory_migration, "get_active_history_uid", lambda c: "conv1")

    assert memory_migration.migrate_character_memories() == []
    assert (dest / "core_memory.md").read_text(encoding="utf-8") == "已經有的"


def test_is_safe_to_run_twice(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _old(tmp_path, "charA", "她記得的事")
    monkeypatch.setattr(memory_migration, "get_active_history_uid", lambda c: "conv1")

    assert memory_migration.migrate_character_memories() == ["charA"]
    assert memory_migration.migrate_character_memories() == []


def test_no_chat_history_directory_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert memory_migration.migrate_character_memories() == []
