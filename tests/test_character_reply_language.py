"""每個角色可以自己決定用什麼語言說話。

先前只有全域的 system_config.player_language。把它設成日文，是為了讓牧瀨紅莉栖
用母語說話——但那會讓 mao_pro 之類的角色也一起講日文。語言屬於角色本身，全域
設定應該只是「沒特別指定時的預設」。

跟 tts_config 的 text_lang 是兩件事：reply_language 是她用什麼語言想事情、寫回覆
（R），text_lang 是用什麼語言發聲（V）。兩者相同時語音路徑會跳過翻譯。

慣例同 tests/test_expression_prompt_gate.py：直接建一個裸的 ServiceContext，只補
construct_system_prompt 會碰到的東西，用 asyncio.run 驅動。
"""

import asyncio
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber.service_context import ServiceContext


def _build(character_language: str, global_language: str) -> ServiceContext:
    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(
        tool_prompts={},
        player_language=global_language,
        player_prompt="",
    )
    context.live2d_model = SimpleNamespace(emo_map={}, emo_str="", motion_str="")
    context.character_config = SimpleNamespace(
        long_term_memory_enabled=False,
        conf_uid="test",
        reply_language=character_language,
    )
    context.stage_director_prompt = ""
    return context


def _prompt(context: ServiceContext) -> str:
    return asyncio.run(context.construct_system_prompt("PERSONA"))


def test_the_character_setting_wins_over_the_global_default():
    result = _prompt(_build("Japanese", "Traditional Chinese (Taiwan)"))

    assert "Always write your reply in Japanese" in result
    assert "Traditional Chinese (Taiwan)" not in result


def test_incoming_character_wins_during_a_character_switch():
    """load_from_config builds the new agent before replacing self.character_config.

    Prompt construction therefore needs the incoming character explicitly; using
    the old one made every Kurisu switch inherit Mao's Traditional Chinese output.
    """
    context = _build("", "Traditional Chinese (Taiwan)")
    incoming = SimpleNamespace(
        long_term_memory_enabled=False,
        conf_uid="kurisu",
        reply_language="Japanese",
    )

    result = asyncio.run(
        context.construct_system_prompt("PERSONA", character_config=incoming)
    )

    assert "Always write your reply in Japanese" in result
    assert "Traditional Chinese (Taiwan)" not in result


def test_the_global_default_applies_when_the_character_says_nothing():
    """沒有自己設定的角色（mao_pro）必須照舊，不能被別的角色的語言波及。"""
    result = _prompt(_build("", "Traditional Chinese (Taiwan)"))

    assert "Always write your reply in Traditional Chinese (Taiwan)" in result


def test_whitespace_is_not_a_language():
    """只有空白的設定要當成沒設，否則會產出一句要求用空字串回答的指令。"""
    result = _prompt(_build("   ", "Traditional Chinese (Taiwan)"))

    assert "Always write your reply in Traditional Chinese (Taiwan)" in result


def test_no_language_block_at_all_when_neither_is_set():
    result = _prompt(_build("", ""))

    assert "Output language" not in result


@pytest.mark.parametrize("language", ["Japanese", "English", "한국어"])
def test_any_language_string_is_passed_through(language):
    """這個欄位是自由字串，不是列舉——不該偷偷正規化或限制成某幾種。"""
    assert f"Always write your reply in {language}" in _prompt(
        _build(language, "Traditional Chinese (Taiwan)")
    )
