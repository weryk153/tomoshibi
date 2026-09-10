from __future__ import annotations

import json

import pytest

from src.open_llm_vtuber import active_character_store


def test_active_character_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    active_character_store.set_active_character_filename("aoi.yaml")

    assert active_character_store.get_active_character_filename() == "aoi.yaml"
    state = json.loads(
        (tmp_path / "characters" / ".active-character.json").read_text(encoding="utf-8")
    )
    assert state == {"version": 1, "filename": "aoi.yaml"}


@pytest.mark.parametrize(
    "filename", ["", "../aoi.yaml", "characters/aoi.yaml", "aoi.json"]
)
def test_active_character_rejects_unsafe_filenames(tmp_path, monkeypatch, filename):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError):
        active_character_store.set_active_character_filename(filename)


def test_corrupt_active_character_state_fails_soft(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state_dir = tmp_path / "characters"
    state_dir.mkdir()
    (state_dir / ".active-character.json").write_text("not json", encoding="utf-8")

    assert active_character_store.get_active_character_filename() is None
