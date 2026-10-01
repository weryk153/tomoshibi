"""角色檔的開機升級：補齊角色擁有的欄位，拿掉不歸角色的設定。"""

from src.open_llm_vtuber import character_settings, conf_editor, conf_upgrade

BASE = """\
system_config:
  player_language: 'Traditional Chinese (Taiwan)'
character_config:
  conf_name: '底稿'
  conf_uid: 'base_uid'
  tts_config:
    tts_model: 'edge_tts'
    edge_tts:
      voice: 'zh-TW-HsiaoChenNeural'
  tts_preprocessor_config:
    translator_config:
      translate_subtitle: false
"""

HAND_WRITTEN = """\
character_config:
  conf_name: '紅莉栖'
  conf_uid: 'kurisu'
  # 這行要留著
  protected_names:
    紅莉栖: ['紅莉棲']
  asr_config:
    asr_model: 'faster_whisper'
  agent_config:
    conversation_agent_choice: 'basic_memory_agent'
  tts_config:
    tts_model: "gpt_sovits_tts"
  tts_preprocessor_config:
    translator_config:
      translate_subtitle: true
"""


def setup(tmp_path, monkeypatch, character=HAND_WRITTEN, name="kurisu.yaml"):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(BASE, encoding="utf-8")
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / name).write_text(character, encoding="utf-8")
    for module in (conf_editor, conf_upgrade, character_settings):
        monkeypatch.setattr(module, "CONF_PATH", "conf.yaml", raising=False)


def test_upgrading_a_character_keeps_its_comments_and_other_keys(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    changes = conf_upgrade.upgrade_character_files()
    text = (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8")
    assert "# 這行要留著" in text
    assert "紅莉棲" in text
    assert "asr_config" not in text
    assert "conversation_agent_choice" not in text
    assert changes["kurisu.yaml"]
    # 第二次什麼都不改。
    assert conf_upgrade.upgrade_character_files() == {}
    assert (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8") == text


def test_missing_owned_fields_get_what_she_uses_today(tmp_path, monkeypatch):
    setup(
        tmp_path,
        monkeypatch,
        character="character_config:\n  conf_name: 'x'\n  conf_uid: 'x'\n",
        name="x.yaml",
    )
    conf_upgrade.upgrade_character_files()
    values = character_settings.effective("x.yaml")
    own = character_settings._load("characters/x.yaml")["character_config"]
    assert own["tts_config"]["tts_model"] == "edge_tts"
    assert own["tts_config"]["edge_tts"]["voice"] == "zh-TW-HsiaoChenNeural"
    assert own["reply_language"] == "Traditional Chinese (Taiwan)"
    assert own["long_term_memory_enabled"] is True
    assert (
        own["tts_preprocessor_config"]["translator_config"]["translate_subtitle"]
        is False
    )
    assert values["reply_language"] == "Traditional Chinese (Taiwan)"


def test_values_a_character_already_has_are_not_overwritten(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    conf_upgrade.upgrade_character_files()
    own = character_settings._load("characters/kurisu.yaml")["character_config"]
    assert own["tts_config"]["tts_model"] == "gpt_sovits_tts"
    assert (
        own["tts_preprocessor_config"]["translator_config"]["translate_subtitle"]
        is True
    )


def test_changing_the_base_afterwards_leaves_other_characters_alone(
    tmp_path, monkeypatch
):
    setup(
        tmp_path,
        monkeypatch,
        character="character_config:\n  conf_name: 'x'\n  conf_uid: 'x'\n",
        name="x.yaml",
    )
    conf_upgrade.upgrade_character_files()
    character_settings.write("conf.yaml", {"voice": "ja-JP-NanamiNeural"})
    assert character_settings.effective("x.yaml")["voice"] == "zh-TW-HsiaoChenNeural"


def test_a_broken_character_file_is_skipped(tmp_path, monkeypatch):
    setup(
        tmp_path, monkeypatch, character="character_config: [oops\n", name="broken.yaml"
    )
    (tmp_path / "characters" / "ok.yaml").write_text(
        "character_config:\n  conf_uid: 'ok'\n", "utf-8"
    )
    (tmp_path / "characters" / "list.yaml").write_text("- 1\n- 2\n", "utf-8")
    changes = conf_upgrade.upgrade_character_files()
    assert "ok.yaml" in changes
    assert (tmp_path / "characters" / "broken.yaml").read_text(
        "utf-8"
    ) == "character_config: [oops\n"


def test_the_base_character_gets_its_reply_language(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    conf_upgrade.upgrade_character_files()
    assert (
        character_settings._load("conf.yaml")["character_config"]["reply_language"]
        == "Traditional Chinese (Taiwan)"
    )


def test_a_new_character_owns_everything_from_the_start(tmp_path, monkeypatch):
    """新建的角色一開始就有自己的一份，之後改底稿角色不會連帶改到她。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.open_llm_vtuber import character_route

    setup(
        tmp_path,
        monkeypatch,
        character="character_config:\n  conf_uid: 'k'\n",
        name="k.yaml",
    )
    monkeypatch.setattr(character_route, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_route, "_is_local_request", lambda r: True)
    monkeypatch.setattr(character_route, "_rescan_skins", lambda: None)
    monkeypatch.setattr(character_route, "_load_model_dict", lambda: [{"name": "mao"}])
    app = FastAPI()
    app.include_router(character_route.init_character_route())
    r = TestClient(app).post(
        "/api/characters",
        json={
            "conf_name": "日和",
            "persona_prompt": "你是日和。",
            "live2d_model_name": "mao",
            "slug": "hiyori",
        },
    )
    assert r.status_code == 200, r.text
    own = character_settings._load("characters/hiyori.yaml")["character_config"]
    assert own["tts_config"]["tts_model"] == "edge_tts"
    assert own["long_term_memory_enabled"] is True
    assert (
        own["tts_preprocessor_config"]["translator_config"]["translate_subtitle"]
        is False
    )
    assert own["reply_language"] == "Traditional Chinese (Taiwan)"
