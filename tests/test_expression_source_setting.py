"""expression_source 是角色自己的設定（角色頁「外觀」區的下拉）：tags 或 background。"""

import pytest
from pydantic import TypeAdapter, ValidationError

from src.open_llm_vtuber import character_settings
from src.open_llm_vtuber.config_manager.character import CharacterConfig
from tests.test_character_settings import client, setup


FIELD = CharacterConfig.model_fields["expression_source"]


def test_tags_is_the_default():
    assert FIELD.default == "tags"


def test_only_the_two_sources_are_accepted():
    check = TypeAdapter(FIELD.annotation)

    assert check.validate_python("background") == "background"
    with pytest.raises(ValidationError):
        check.validate_python("vibes")


def test_it_is_read_with_the_other_settings(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)

    got = http.get("/api/characters/kurisu.yaml/settings").json()["settings"]

    assert got["expression_source"] == "tags"


def test_it_is_written_to_the_characters_own_file(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)

    saved = http.post(
        "/api/characters/kurisu.yaml/settings", json={"expression_source": "background"}
    ).json()

    assert saved["ok"] is True and saved["reload_required"] is True
    assert saved["settings"]["expression_source"] == "background"
    text = (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8")
    assert "expression_source: background" in text
    assert "# 手寫的註解" in text
    assert "expression_source" not in (tmp_path / "conf.yaml").read_text("utf-8")


def test_the_base_character_gets_one_line(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    before = (tmp_path / "conf.yaml").read_text("utf-8").splitlines()

    character_settings.write("conf.yaml", {"expression_source": "background"})

    after = (tmp_path / "conf.yaml").read_text("utf-8").splitlines()
    assert "  expression_source: 'background'" in after
    assert len(after) == len(before) + 1
    assert (
        character_settings.effective("conf.yaml")["expression_source"] == "background"
    )


def test_anything_else_is_refused(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    before = (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8")
    url = "/api/characters/kurisu.yaml/settings"

    assert http.post(url, json={"expression_source": "vibes"}).status_code == 400
    assert http.post(url, json={"expression_source": True}).status_code == 400
    assert http.post(url, json={"translate_subtitle": "background"}).status_code == 400
    assert (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8") == before


def test_the_character_list_carries_it(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)

    characters = http.get("/api/characters").json()["characters"]

    assert {c["filename"]: c["expression_source"] for c in characters} == {
        "conf.yaml": "tags",
        "kurisu.yaml": "tags",
    }
