"""service_context 建立翻譯器時要帶上目前角色的專有名詞名單。

這是整條線的最後一個接點：名單存在角色設定裡，翻譯器在這裡被建立。
"""

from types import SimpleNamespace

from src.open_llm_vtuber.service_context import ServiceContext


def _context_with(protected_names):
    context = ServiceContext.__new__(ServiceContext)
    context.character_config = SimpleNamespace(protected_names=protected_names)
    return context


def test_subtitle_translator_is_built_with_the_characters_names(monkeypatch):
    captured = {}

    def _capture(provider, cfg, protected_names=None):
        captured["protected_names"] = protected_names
        return SimpleNamespace()

    monkeypatch.setattr(
        "src.open_llm_vtuber.service_context.TranslateFactory.get_translator",
        _capture,
    )

    context = _context_with({"愛徠": ["愛萊"]})
    translator_config = SimpleNamespace(
        translate_provider="llm",
        subtitle_target_lang="德文",
        llm=SimpleNamespace(model_dump=lambda: {"target_lang": "繁體中文"}),
    )
    context._build_subtitle_translator(translator_config)

    assert captured["protected_names"] == {"愛徠": ["愛萊"]}
