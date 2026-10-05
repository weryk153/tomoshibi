"""service_context 建立翻譯器時要帶上目前角色的口頭禪名單。

AUDIO 翻譯器一定要帶：它是把回覆轉成角色語音語言的那個，口頭禪的「目標寫法」
正是為它寫的（見 CharacterConfig.catchphrases 的註解）。

SUBTITLE 翻譯器只在「無害」時才帶：口頭禪的目標寫法是為聲音語言寫的，字幕
目標是玩家語言，通常跟聲音語言不同；只有字幕目標跟角色來源語言同屬一個語言桶
時，conversation_utils 才會整句跳過字幕翻譯（R == 字幕目標），口頭禪規則永遠
不會被送進模型，這時候帶著它才真的無害。
"""

from types import SimpleNamespace

from src.open_llm_vtuber.service_context import ServiceContext


def _context_with(reply_language, catchphrases):
    context = ServiceContext.__new__(ServiceContext)
    context.character_config = SimpleNamespace(
        protected_names={},
        reply_language=reply_language,
        catchphrases=catchphrases,
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


def test_subtitle_translator_gets_catchphrases_when_target_matches_source(
    monkeypatch,
):
    """Pekora 的情況：回覆是繁中，字幕也翻成繁中（跟玩家語言一樣）——同一個
    語言桶，字幕翻譯逐句會被跳過，帶著口頭禪無害。"""
    captured = _capture(monkeypatch)
    context = _context_with("Traditional Chinese (Taiwan)", {"peko": "ぺこ"})
    translator_config = SimpleNamespace(
        translate_provider="llm",
        llm=SimpleNamespace(model_dump=lambda: {"target_lang": "繁體中文"}),
    )

    context._build_subtitle_translator(
        translator_config, "Traditional Chinese (Taiwan)"
    )

    assert captured["catchphrases"] == {"peko": "ぺこ"}


def test_subtitle_translator_does_not_get_catchphrases_when_target_differs(
    monkeypatch,
):
    """角色回覆日文、字幕卻翻成英文：口頭禪的寫法（ぺこ）是為日文語音寫的，
    塞進英文字幕的 prompt 會把日文誤植進去，不是無害的情況，所以不帶。"""
    captured = _capture(monkeypatch)
    context = _context_with("Japanese", {"peko": "ぺこ"})
    translator_config = SimpleNamespace(
        translate_provider="llm",
        llm=SimpleNamespace(model_dump=lambda: {"target_lang": "英文"}),
    )

    context._build_subtitle_translator(translator_config, "English")

    assert captured["catchphrases"] is None


def test_subtitle_translator_with_no_catchphrases_configured(monkeypatch):
    captured = _capture(monkeypatch)
    context = _context_with("Traditional Chinese (Taiwan)", {})
    translator_config = SimpleNamespace(
        translate_provider="llm",
        llm=SimpleNamespace(model_dump=lambda: {"target_lang": "繁體中文"}),
    )

    context._build_subtitle_translator(
        translator_config, "Traditional Chinese (Taiwan)"
    )

    assert not captured["catchphrases"]


def test_audio_translator_always_gets_the_characters_catchphrases(monkeypatch):
    """AUDIO 引擎的目標就是角色的語音語言——口頭禪對照表正是為它寫的，
    一定要帶，不像字幕引擎需要先判斷目標語言是否相符。"""
    captured = _capture(monkeypatch)
    context = _context_with("Traditional Chinese (Taiwan)", {"peko": "ぺこ"})
    context.translate_engine = None
    context.subtitle_translate_engine = None
    context._audio_translate_voice_lang = None
    context.character_config.tts_preprocessor_config = SimpleNamespace(
        translator_config=None
    )
    translator_config = SimpleNamespace(
        translate_audio=True,
        translate_subtitle=False,
        translate_provider="llm",
        llm=SimpleNamespace(model_dump=lambda: {"target_lang": "日文"}),
    )

    context.init_translate(translator_config, voice_lang="ja", player_language=None)

    assert captured["catchphrases"] == {"peko": "ぺこ"}
