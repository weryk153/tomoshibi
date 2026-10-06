"""角色頁的翻譯審核建議：讀 summary、一鍵把建議加進角色檔，其他欄位不動。"""

import json

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import character_route, character_settings, conf_editor
from src.open_llm_vtuber.translate.audit import AuditStore

BASE = """\
system_config:
  player_language: 'zh-TW'
character_config:
  conf_name: '底稿'
  conf_uid: 'base_uid'
  persona_prompt: |
    你是底稿。
  bilingual_subtitle: True # 手寫的註解
"""

ORIGINAL = {
    "conf_uid": "pekora",
    "conf_name": "兔田佩克拉",
    "character_name": "佩克拉",
    "persona_prompt": "你是佩克拉。\n",
    "live2d_model_name": "mao_pro",
    "protected_names": {"兔田佩克拉": ["兔田佩可拉"]},
    "catchphrases": {"konpeko": "こんぺこ"},
    "long_term_memory_enabled": False,
    "translation_audit": True,
    "tts_preprocessor_config": {"translator_config": {"translate_subtitle": False}},
    "tts_config": {
        "tts_model": "gpt_sovits_tts",
        "gpt_sovits_tts": {
            "api_url": "http://127.0.0.1:9880/tts",
            "text_lang": "ja",
            "ref_audio_path": "ref/pekora.wav",
        },
    },
}


def _entry(names=None, phrases=None, issues=()):
    return {
        "time": "2026-10-06T12:00:00",
        "original": "佩克拉peko",
        "translated": "ペコラぺこ",
        "target_lang": "ja",
        "issues": list(issues),
        "suggest": {
            "protected_names": names or {},
            "catchphrases": phrases or {},
        },
    }


def _client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(BASE, encoding="utf-8")
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "pekora.yaml").write_text(
        "# 佩克拉的檔案\n"
        + yaml.safe_dump({"character_config": ORIGINAL}, allow_unicode=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(conf_editor, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_route, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_settings, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_route, "_is_local_request", lambda r: True)
    monkeypatch.setattr(character_route, "_mark_if_active", lambda filename: None)
    store = AuditStore(tmp_path / "chat_history" / "pekora" / "translation_audit")
    issue = [{"kind": "name", "detail": "x"}]
    store.record(
        [
            _entry({"ペコラ": "ぺこら"}, {"peko": "ぺこ"}, issue),
            _entry({"ペコラ": "ぺこら"}, {"peko": "ぺこ"}, issue),
            _entry({"兔田佩可拉": "兔田佩克拉"}),  # 已經在角色設定裡
            _entry({"兔田佩可拉": "兔田佩克拉"}),
            _entry(phrases={"konpeko": "こんぺこ"}),  # 已經在角色設定裡
            _entry(phrases={"konpeko": "こんぺこ"}),
            _entry(phrases={"nya": "にゃ"}),  # 只出現一次
        ]
    )
    app = FastAPI()
    app.include_router(character_route.init_character_route())
    return TestClient(app)


URL = "/api/characters/pekora.yaml/translation-audit"


def _saved(tmp_path):
    return yaml.safe_load((tmp_path / "characters" / "pekora.yaml").read_text("utf-8"))[
        "character_config"
    ]


def test_get_lists_repeated_suggestions_not_yet_in_the_character(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    body = http.get(URL).json()
    assert body["ok"] is True
    assert body["enabled"] is True
    assert body["audited"] == 7
    assert body["flagged"] == 2
    assert body["suggestions"] == {
        "protected_names": [{"source": "ペコラ", "target": "ぺこら", "count": 2}],
        "catchphrases": [{"source": "peko", "target": "ぺこ", "count": 2}],
    }
    assert [line["original"] for line in body["suspicious"]] == ["佩克拉peko"] * 2


def test_get_without_any_audit_yet(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    body = http.get("/api/characters/conf.yaml/translation-audit").json()
    assert body["ok"] is True
    assert body["enabled"] is False
    assert body["audited"] == 0
    assert body["suggestions"] == {"protected_names": [], "catchphrases": []}


def test_get_unknown_character(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    assert http.get("/api/characters/nobody.yaml/translation-audit").status_code == 404


def test_adding_suggestions_keeps_every_other_field(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    for kind, source, target in (
        ("protected_names", "ペコラ", "ぺこら"),
        ("catchphrases", "peko", "ぺこ"),
    ):
        response = http.post(
            URL + "/accept", json={"kind": kind, "source": source, "target": target}
        )
        assert response.status_code == 200, response.text

    saved = _saved(tmp_path)
    assert saved["protected_names"] == {
        "兔田佩克拉": ["兔田佩可拉"],
        "ぺこら": ["ペコラ"],
    }
    assert saved["catchphrases"] == {"konpeko": "こんぺこ", "peko": "ぺこ"}
    for key in ORIGINAL:
        if key not in ("protected_names", "catchphrases"):
            assert saved[key] == ORIGINAL[key], key
    text = (tmp_path / "characters" / "pekora.yaml").read_text("utf-8")
    assert text.startswith("# 佩克拉的檔案")
    # 加過的建議不再列出來
    assert http.get(URL).json()["suggestions"] == {
        "protected_names": [],
        "catchphrases": [],
    }


def test_adding_a_misspelling_to_a_name_already_protected(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    AuditStore(tmp_path / "chat_history" / "pekora" / "translation_audit").record(
        [_entry({"兔田佩克啦": "兔田佩克拉"})] * 2
    )
    response = http.post(
        URL + "/accept",
        json={
            "kind": "protected_names",
            "source": "兔田佩克啦",
            "target": "兔田佩克拉",
        },
    )
    assert response.status_code == 200, response.text
    assert _saved(tmp_path)["protected_names"] == {
        "兔田佩克拉": ["兔田佩可拉", "兔田佩克啦"]
    }


def test_only_suggestions_the_audit_made_can_be_added(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    for body in (
        {"kind": "catchphrases", "source": "hello", "target": "やあ"},
        {"kind": "persona_prompt", "source": "peko", "target": "ぺこ"},
        {"kind": "catchphrases", "source": "peko"},
        [],
    ):
        assert http.post(URL + "/accept", json=body).status_code == 400
    assert _saved(tmp_path)["catchphrases"] == {"konpeko": "こんぺこ"}


def test_adding_to_the_base_character_keeps_the_conf_comments(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    AuditStore(tmp_path / "chat_history" / "base_uid" / "translation_audit").record(
        [_entry(phrases={"peko": "ぺこ"})] * 2
    )
    response = http.post(
        "/api/characters/conf.yaml/translation-audit/accept",
        json={"kind": "catchphrases", "source": "peko", "target": "ぺこ"},
    )
    assert response.status_code == 200, response.text
    text = (tmp_path / "conf.yaml").read_text("utf-8")
    assert "# 手寫的註解" in text
    assert yaml.safe_load(text)["character_config"]["catchphrases"] == {"peko": "ぺこ"}


def test_the_switch_is_a_character_setting(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    url = "/api/characters/conf.yaml/settings"
    assert http.get(url).json()["settings"]["translation_audit"] is False
    saved = http.post(url, json={"translation_audit": True}).json()
    assert saved["settings"]["translation_audit"] is True
    assert "  translation_audit: True" in (tmp_path / "conf.yaml").read_text("utf-8")
    listed = http.get("/api/characters").json()["characters"]
    by_file = {c["filename"]: c for c in listed}
    assert by_file["pekora.yaml"]["translation_audit"] is True


def test_the_character_owns_the_switch():
    assert character_settings.OWNED["translation_audit"] == ("translation_audit",)
    assert "translation_audit" in character_settings.TOGGLES
    assert character_settings.DEFAULTS["translation_audit"] is False


def test_summary_file_is_plain_json(tmp_path, monkeypatch):
    _client(tmp_path, monkeypatch)
    path = tmp_path / "chat_history" / "pekora" / "translation_audit" / "summary.json"
    assert json.loads(path.read_text("utf-8"))["audited"] == 7
