"""角色擁有的設定：找得到角色檔、讀得出實際值、寫回去不弄掉註解。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import character_route, character_settings, conf_editor

BASE = """\
system_config:
  player_language: 'zh-TW'
character_config:
  conf_name: '底稿'
  conf_uid: 'base_uid'
  persona_prompt: |
    你是底稿。
  tts_config:
    tts_model: 'edge_tts' # 預設引擎
  tts_preprocessor_config:
    translator_config:
      translate_subtitle: false
"""

KURISU = """\
character_config:
  conf_name: '紅莉栖'
  conf_uid: 'kurisu'
  # 手寫的註解
  persona_prompt: |
    你是紅莉栖。
  tts_config:
    tts_model: 'gpt_sovits_tts'
"""


def setup(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(BASE, encoding="utf-8")
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "kurisu.yaml").write_text(KURISU, encoding="utf-8")
    monkeypatch.setattr(conf_editor, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_route, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_settings, "CONF_PATH", "conf.yaml")


def test_a_character_is_found_by_its_conf_uid(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    assert character_settings.filename_for_uid("base_uid") == "conf.yaml"
    assert character_settings.filename_for_uid("kurisu") == "kurisu.yaml"
    assert character_settings.filename_for_uid("nobody") is None


def test_effective_values_merge_the_base_under_the_character(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    kurisu = character_settings.effective("kurisu.yaml")
    assert kurisu["tts_model"] == "gpt_sovits_tts"
    assert kurisu["translate_subtitle"] is False
    assert kurisu["long_term_memory_enabled"] is True


def test_writing_a_toggle_keeps_comments_and_creates_missing_blocks(
    tmp_path, monkeypatch
):
    setup(tmp_path, monkeypatch)
    character_settings.write(
        "kurisu.yaml", {"translate_subtitle": True, "long_term_memory_enabled": False}
    )
    text = (tmp_path / "characters" / "kurisu.yaml").read_text(encoding="utf-8")
    assert "# 手寫的註解" in text
    assert character_settings.effective("kurisu.yaml")["translate_subtitle"] is True
    assert (
        character_settings.effective("kurisu.yaml")["long_term_memory_enabled"] is False
    )
    # 底稿沒被碰。
    assert "translate_subtitle: false" in (tmp_path / "conf.yaml").read_text("utf-8")


def test_writing_the_base_character_goes_to_conf_yaml(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    character_settings.write("conf.yaml", {"long_term_memory_enabled": False})
    text = (tmp_path / "conf.yaml").read_text(encoding="utf-8")
    assert "long_term_memory_enabled: False" in text
    assert "# 預設引擎" in text


def client(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    monkeypatch.setattr(character_route, "_is_local_request", lambda r: True)
    app = FastAPI()
    app.include_router(character_route.init_character_route())
    return TestClient(app)


def test_settings_endpoint_reads_and_writes(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    got = http.get("/api/characters/kurisu.yaml/settings").json()
    assert got["settings"] == {
        "translate_subtitle": False,
        "long_term_memory_enabled": True,
        "actions_enabled": False,
        "bilingual_subtitle": False,
        "translation_audit": False,
        "expression_source": "tags",
        "proactive_when_unanswered": "keep_talking",
    }
    saved = http.post(
        "/api/characters/kurisu.yaml/settings", json={"translate_subtitle": True}
    ).json()
    assert saved["ok"] is True and saved["reload_required"] is True
    assert saved["settings"]["translate_subtitle"] is True


def test_settings_endpoint_rejects_bad_input(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    before = (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8")
    url = "/api/characters/kurisu.yaml/settings"
    assert http.post(url, json={"translate_subtitle": "yes"}).status_code == 400
    assert http.post(url, json={"tts_model": "edge_tts"}).status_code == 400
    assert http.post(url, json={}).status_code == 400
    assert (
        http.post(
            "/api/characters/nobody.yaml/settings", json={"translate_subtitle": True}
        ).status_code
        == 404
    )
    assert http.post(
        "/api/characters/..%2Fconf.yaml/settings", json={"translate_subtitle": True}
    ).status_code in (400, 404)
    assert (tmp_path / "characters" / "kurisu.yaml").read_text("utf-8") == before


CONF_WITH_SECTIONS = """\
system_config:
  player_language: 'zh-TW'
character_config:
  conf_uid: 'base_uid'
  tts_preprocessor_config:
    translator_config:
      translate_audio: True # 註解
      translate_subtitle: False

  # 直播平台集成
live_config:
  enabled: False
"""


def test_writing_the_base_character_changes_only_its_own_lines(tmp_path, monkeypatch):
    """conf.yaml 是使用者手寫的主設定：只改（或插入）那一行，其餘逐字不動。
    整份 round-trip 會把下一段的標題註解黏到新欄位上，還把 True 改寫成 true。"""
    setup(tmp_path, monkeypatch)
    (tmp_path / "conf.yaml").write_text(CONF_WITH_SECTIONS, encoding="utf-8")

    character_settings.write(
        "conf.yaml", {"long_term_memory_enabled": False, "translate_subtitle": True}
    )

    after = (tmp_path / "conf.yaml").read_text(encoding="utf-8").splitlines()
    before = CONF_WITH_SECTIONS.splitlines()
    assert "      translate_audio: True # 註解" in after
    assert "      translate_subtitle: True" in after
    assert "  long_term_memory_enabled: False" in after
    assert after.index("  # 直播平台集成") == after.index("live_config:") - 1
    assert len(after) == len(before) + 1
    assert (
        character_settings.effective("conf.yaml")["long_term_memory_enabled"] is False
    )


def test_the_action_switch_is_a_character_setting(tmp_path, monkeypatch):
    http = client(tmp_path, monkeypatch)
    assert (
        http.get("/api/characters/kurisu.yaml/settings").json()["settings"][
            "actions_enabled"
        ]
        is False
    )
    saved = http.post(
        "/api/characters/kurisu.yaml/settings", json={"actions_enabled": True}
    ).json()
    assert saved["settings"]["actions_enabled"] is True
    assert character_settings.effective("kurisu.yaml")["actions_enabled"] is True


def test_what_she_does_when_nobody_answers_is_a_character_setting(
    tmp_path, monkeypatch
):
    http = client(tmp_path, monkeypatch)
    url = "/api/characters/kurisu.yaml/settings"
    saved = http.post(url, json={"proactive_when_unanswered": "wait"}).json()
    assert saved["settings"]["proactive_when_unanswered"] == "wait"
    assert (
        http.post(url, json={"proactive_when_unanswered": "sleep"}).status_code == 400
    )
