"""回覆語言要跟著角色走，沒設就退回玩家層級的設定。

single_conversation 在每一則 SentenceOutput 上呼叫 _effective_output_language()，
但那個函式從來沒有被定義過——呼叫寫了，實作沒寫。它被外層的 except Exception
接住，只留一行 log，所以「她一句話都回不出來」看起來像模型的問題。
"""

from types import SimpleNamespace

from src.open_llm_vtuber.conversations.single_conversation import (
    _effective_output_language,
)


def _context(reply_language=None, player_language=None):
    return SimpleNamespace(
        character_config=SimpleNamespace(reply_language=reply_language),
        system_config=SimpleNamespace(player_language=player_language),
    )


def test_uses_the_characters_reply_language():
    assert _effective_output_language(_context(reply_language="ja")) == "ja"


def test_falls_back_to_the_player_language():
    ctx = _context(reply_language=None, player_language="zh-TW")
    assert _effective_output_language(ctx) == "zh-TW"


def test_character_language_wins_over_the_player_default():
    ctx = _context(reply_language="ko", player_language="zh-TW")
    assert _effective_output_language(ctx) == "ko"


def test_empty_string_counts_as_unset():
    # YAML 的空欄位讀出來是 ''，不是 None。當成「沒設」才會退回玩家設定，
    # 否則語言變成空字串，normalize 就拿不到任何依據。
    ctx = _context(reply_language="", player_language="ja")
    assert _effective_output_language(ctx) == "ja"


def test_returns_empty_when_nothing_is_configured():
    assert _effective_output_language(_context()) == ""
