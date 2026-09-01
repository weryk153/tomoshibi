"""工廠要把角色的專有名詞名單交給 LLM 翻譯器。

沒有這一段，名單就停在設定裡，翻譯路徑仍然什麼都不知道。
"""

from src.open_llm_vtuber.translate.translate_factory import TranslateFactory


def _llm_config() -> dict:
    return {
        "api_endpoint": "http://translator.test/v1/chat/completions",
        "model": "local-model",
        "target_lang": "繁體中文",
        "timeout": 17,
    }


def test_llm_translator_receives_the_supplied_names():
    translator = TranslateFactory.get_translator(
        "llm",
        _llm_config(),
        protected_names={"愛徠": ["愛萊"]},
    )

    assert translator.protected_names == {"愛徠": ["愛萊"]}


def test_llm_translator_defaults_to_no_protected_names():
    """沒給就是空的——大多數角色不需要這個功能。"""
    translator = TranslateFactory.get_translator("llm", _llm_config())

    assert translator.protected_names == {}
