"""GET /api/perf's engine_overrides_by_character map.

A character file's own asr_config/tts_config replaces conf.yaml's when that
character is loaded, so an engine picked on the TTS/ASR settings tab can be
silently swapped back on the next character switch. The tab had nothing on
screen to explain that: you選 GPT-SoVITS, it saves, and the character keeps
speaking with the built-in voice. This map is what lets the UI name the
conflict, so it has to report only real overrides — a false positive puts a
scary warning on a tab that is working fine.

Same convention as tests/test_perf_gpt_sovits_fields.py: call the route
module's helper directly against a tmp_path tree (monkeypatch.chdir), never a
real request or the user's real characters/.
"""

from src.open_llm_vtuber.perf_route import _engine_overrides_by_character


def _write_character(tmp_path, filename: str, body: str) -> None:
    directory = tmp_path / "characters"
    directory.mkdir(exist_ok=True)
    (directory / filename).write_text(body, encoding="utf-8")


def test_reports_only_characters_that_pin_an_engine(tmp_path, monkeypatch):
    _write_character(
        tmp_path,
        "pinned.yaml",
        "character_config:\n"
        "  conf_name: 牧瀨紅莉栖\n"
        "  tts_config:\n"
        "    tts_model: gpt_sovits_tts\n"
        "    gpt_sovits_tts:\n"
        "      api_url: 'http://127.0.0.1:9880/tts'\n",
    )
    # Inherits both engines from conf.yaml — nothing is overridden, so warning
    # about it would be a lie.
    _write_character(
        tmp_path,
        "inherits.yaml",
        "character_config:\n"
        "  conf_name: 普通角色\n"
        "  persona_prompt: |\n"
        "    你好。\n",
    )
    monkeypatch.chdir(tmp_path)

    assert _engine_overrides_by_character() == {
        "牧瀨紅莉栖": {"tts_model": "gpt_sovits_tts"},
    }


def test_reports_asr_and_tts_independently(tmp_path, monkeypatch):
    _write_character(
        tmp_path,
        "both.yaml",
        "character_config:\n"
        "  conf_name: 雙釘\n"
        "  asr_config:\n"
        "    asr_model: groq_whisper_asr\n"
        "  tts_config:\n"
        "    tts_model: edge_tts\n",
    )
    _write_character(
        tmp_path,
        "asr-only.yaml",
        "character_config:\n"
        "  conf_name: 只釘辨識\n"
        "  asr_config:\n"
        "    asr_model: azure_asr\n"
        "  tts_config:\n"
        "    edge_tts:\n"
        "      voice: zh-CN-XiaoyiNeural\n",
    )
    monkeypatch.chdir(tmp_path)

    # asr-only has a tts_config block but no tts_model leaf: a present block is
    # not an override, only a pinned engine is.
    assert _engine_overrides_by_character() == {
        "雙釘": {"asr_model": "groq_whisper_asr", "tts_model": "edge_tts"},
        "只釘辨識": {"asr_model": "azure_asr"},
    }


def test_falls_back_to_the_filename_when_conf_name_is_absent(tmp_path, monkeypatch):
    _write_character(
        tmp_path,
        "nameless.yaml",
        "character_config:\n  tts_config:\n    tts_model: gpt_sovits_tts\n",
    )
    monkeypatch.chdir(tmp_path)

    assert _engine_overrides_by_character() == {
        "nameless": {"tts_model": "gpt_sovits_tts"},
    }


def test_a_broken_character_file_does_not_hide_the_others(tmp_path, monkeypatch):
    """One unparseable file must not blank the whole map — the remaining
    characters' warnings still need to appear."""
    _write_character(tmp_path, "broken.yaml", "character_config:\n  - [unclosed\n")
    _write_character(
        tmp_path,
        "good.yaml",
        "character_config:\n"
        "  conf_name: 好的\n"
        "  tts_config:\n"
        "    tts_model: gpt_sovits_tts\n",
    )
    monkeypatch.chdir(tmp_path)

    assert _engine_overrides_by_character() == {"好的": {"tts_model": "gpt_sovits_tts"}}


def test_missing_characters_directory_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert _engine_overrides_by_character() == {}
