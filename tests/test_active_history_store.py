from __future__ import annotations

import json

import pytest

from src.open_llm_vtuber import active_history_store


def test_active_history_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    active_history_store.set_active_history_uid("kurisu", "2026-08-17_18-49-17_abc123")

    assert (
        active_history_store.get_active_history_uid("kurisu")
        == "2026-08-17_18-49-17_abc123"
    )
    state = json.loads(
        (tmp_path / "chat_history" / ".active-history.json").read_text(encoding="utf-8")
    )
    assert state == {
        "version": 1,
        "histories": {"kurisu": "2026-08-17_18-49-17_abc123"},
    }


def test_active_history_is_tracked_per_character(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    active_history_store.set_active_history_uid("kurisu", "history-a")
    active_history_store.set_active_history_uid("task3", "history-b")

    assert active_history_store.get_active_history_uid("kurisu") == "history-a"
    assert active_history_store.get_active_history_uid("task3") == "history-b"
    assert active_history_store.get_active_history_uid("nobody") is None


def test_clearing_one_character_keeps_the_others(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    active_history_store.set_active_history_uid("kurisu", "history-a")
    active_history_store.set_active_history_uid("task3", "history-b")

    active_history_store.clear_active_history_uid("kurisu")

    assert active_history_store.get_active_history_uid("kurisu") is None
    assert active_history_store.get_active_history_uid("task3") == "history-b"


def test_clearing_an_unknown_character_is_a_no_op(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    active_history_store.clear_active_history_uid("kurisu")

    assert active_history_store.get_active_history_uid("kurisu") is None


@pytest.mark.parametrize(
    "history_uid", ["", "   ", "..", "../escape", "sub/dir", "sub\\dir"]
)
def test_active_history_rejects_unsafe_uids(tmp_path, monkeypatch, history_uid):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError):
        active_history_store.set_active_history_uid("kurisu", history_uid)


@pytest.mark.parametrize("conf_uid", ["", "   ", "..", "../escape", "sub/dir"])
def test_active_history_rejects_unsafe_conf_uids(tmp_path, monkeypatch, conf_uid):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError):
        active_history_store.set_active_history_uid(conf_uid, "history-a")


def test_corrupt_active_history_state_fails_soft(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "chat_history"
    state_dir.mkdir()
    (state_dir / ".active-history.json").write_text("not json", encoding="utf-8")

    assert active_history_store.get_active_history_uid("kurisu") is None


def test_corrupt_state_is_replaced_rather_than_crashing_the_write(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "chat_history"
    state_dir.mkdir()
    (state_dir / ".active-history.json").write_text("not json", encoding="utf-8")

    active_history_store.set_active_history_uid("kurisu", "history-a")

    assert active_history_store.get_active_history_uid("kurisu") == "history-a"


def test_a_poisoned_entry_does_not_leak_out(tmp_path, monkeypatch):
    """State on disk is untrusted input: a traversal uid must not be returned."""
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "chat_history"
    state_dir.mkdir()
    (state_dir / ".active-history.json").write_text(
        json.dumps({"version": 1, "histories": {"kurisu": "../../etc/passwd"}}),
        encoding="utf-8",
    )

    assert active_history_store.get_active_history_uid("kurisu") is None
