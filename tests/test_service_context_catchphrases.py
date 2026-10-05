"""service_context 建立翻譯器時，口頭禪只交給音訊翻譯器。

音訊翻譯器把回覆轉成角色的語音語言，口頭禪的「目標寫法」正是為它寫的（見
CharacterConfig.catchphrases 的註解）。字幕翻譯器翻成玩家看的語言，跟那個
寫法無關，所以不帶。換角色時讀新角色的名單，見
test_translate_follows_character_switch.py。
"""

from types import SimpleNamespace

from src.open_llm_vtuber.service_context import ServiceContext


def _context_with(catchphrases):
    context = ServiceContext()
    context.character_config = SimpleNamespace(
        protected_names={},
        catchphrases=catchphrases,
        tts_preprocessor_config=SimpleNamespace(translator_config=None),
    )
    return context


def _capture(monkeypatch):
    captured = {}

    def _get_translator(provider, cfg, protected_names=None, catchphrases=None):
        captured["catchphrases"] = catchphrases
        return SimpleNamespace()

    monkeypatch.setattr(
        "src.open_llm_vtuber.service_context.TranslateFactory.get_translator",
        _get_translator,
    )
    return captured


def _translator_config(translate_audio, translate_subtitle):
    return SimpleNamespace(
        translate_audio=translate_audio,
        translate_subtitle=translate_subtitle,
        translate_provider="llm",
        llm=SimpleNamespace(model_dump=lambda: {"target_lang": "日文"}),
    )


def test_audio_translator_gets_the_characters_catchphrases(monkeypatch):
    captured = _capture(monkeypatch)
    context = _context_with({"nya": "にゃ"})

    context.init_translate(
        _translator_config(translate_audio=True, translate_subtitle=False),
        voice_lang="ja",
    )

    assert captured["catchphrases"] == {"nya": "にゃ"}


def test_subtitle_translator_does_not_get_catchphrases(monkeypatch):
    captured = _capture(monkeypatch)
    context = _context_with({"nya": "にゃ"})

    context.init_translate(
        _translator_config(translate_audio=False, translate_subtitle=True),
        player_language="zh-TW",
    )

    assert captured["catchphrases"] is None
