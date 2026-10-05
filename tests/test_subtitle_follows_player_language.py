"""字幕翻成「你看的語言」；開不開是角色自己的事。"""

import pytest

from src.open_llm_vtuber.translate.deeplx import (
    resolve_deepl_target_lang,
    subtitle_target,
)


@pytest.mark.parametrize(
    "player_language, name, code",
    [
        ("zh-TW", "繁體中文", "ZH-HANT"),
        ("Traditional Chinese (Taiwan)", "繁體中文", "ZH-HANT"),
        ("zh-CN", "簡體中文", "ZH-HANS"),
        ("en", "英文", "EN-US"),
        ("ja", "日文", "JA"),
        ("ko", "韓文", "KO"),
    ],
)
def test_subtitle_target_follows_what_you_read(player_language, name, code):
    assert subtitle_target(player_language) == name
    assert resolve_deepl_target_lang(subtitle_target(player_language)) == code


def test_turning_subtitles_on_needs_no_stored_target():
    from src.open_llm_vtuber.config_manager.tts_preprocessor import TranslatorConfig

    config = TranslatorConfig.model_validate(
        {
            "translate_audio": False,
            "translate_provider": "llm",
            "translate_subtitle": True,
            "llm": {
                "api_endpoint": "http://127.0.0.1:1234/v1",
                "model": "m",
                "target_lang": "日文",
            },
        }
    )
    assert config.translate_subtitle is True


def test_the_language_you_read_can_be_read_back(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.open_llm_vtuber import conf_editor, player_route

    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(
        "system_config:\n  player_language: 'zh-TW'\n", "utf-8"
    )
    monkeypatch.setattr(conf_editor, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(player_route, "CONF_PATH", "conf.yaml", raising=False)
    monkeypatch.setattr(player_route, "_is_local_request", lambda r: True)
    app = FastAPI()
    app.include_router(player_route.init_player_route())
    assert TestClient(app).get("/api/player-language").json()["language"] == "zh-TW"


def test_the_subtitle_translator_targets_the_language_being_loaded(monkeypatch):
    """重新載入設定時，self.system_config 要到最後才換成新的；字幕翻譯要用這次
    載入的「你看的語言」，不是上一份的。"""
    from types import SimpleNamespace

    from src.open_llm_vtuber.service_context import ServiceContext

    captured = {}

    def capture(provider, cfg, protected_names=None, catchphrases=None):
        captured.update(cfg)
        return SimpleNamespace()

    monkeypatch.setattr(
        "src.open_llm_vtuber.service_context.TranslateFactory.get_translator", capture
    )
    context = ServiceContext.__new__(ServiceContext)
    context.character_config = SimpleNamespace(protected_names={})
    context.system_config = SimpleNamespace(player_language="ja")
    translator_config = SimpleNamespace(
        translate_provider="llm",
        llm=SimpleNamespace(model_dump=lambda: {"target_lang": "日文"}),
    )

    context._build_subtitle_translator(translator_config, "zh-TW")

    assert captured["target_lang"] == "繁體中文"
