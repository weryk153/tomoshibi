"""The agent's memory must store the same script the user is shown.

Display and history both run replies through normalize_output_language_variant
(single_conversation does it for display_text and tts_text). Memory did not.
That made a self-reinforcing loop: a turn that drifted into Simplified was shown
and stored as Traditional but *remembered* as Simplified, so on the next turn the
model read its own past speech in the script it is supposed to have stopped
using — and kept drifting.

Caught in the debug log as one proactive anchor block holding both scripts at
once: the first sentence Traditional, the rest Simplified, for a turn whose
history file was fully Traditional.

The conversion only touches Chinese characters, so it does not fight the persona
rule about replying in the user's current language — a Japanese or English reply
passes through untouched.
"""

from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent

TAIWAN = "Traditional Chinese (Taiwan)"


def _agent(player_language: str) -> BasicMemoryAgent:
    agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
    agent._memory = []
    agent._player_language = player_language
    return agent


def test_a_simplified_reply_is_remembered_in_the_script_the_user_saw():
    agent = _agent(TAIWAN)

    agent._add_message("我这边反应有点延迟，看来是系统刚刚加载的。", "assistant")

    assert agent._memory[-1]["content"] == "我這邊反應有點延遲，看來是系統剛剛載入的。"


def test_a_mixed_script_reply_is_made_consistent():
    """The real failure was one turn holding both scripts, not a fully
    Simplified one."""
    agent = _agent(TAIWAN)

    agent._add_message("「測試」這種話。我这边反应有点延迟。", "assistant")

    assert "我这边反应" not in agent._memory[-1]["content"]
    assert "我這邊反應" in agent._memory[-1]["content"]


def test_a_japanese_reply_is_left_alone():
    """The persona now replies in whatever language the user is using. Script
    normalisation must not touch a non-Chinese reply."""
    agent = _agent(TAIWAN)
    line = "こっちの反応がちょっと遅れてるみたいですね。"

    agent._add_message(line, "assistant")

    assert agent._memory[-1]["content"] == line


def test_nothing_is_converted_when_no_language_is_configured():
    """normalize_output_language_variant only converts for Taiwan zh; with an
    empty setting the reply must pass through rather than being silently
    rewritten."""
    agent = _agent("")
    line = "我这边反应有点延迟。"

    agent._add_message(line, "assistant")

    assert agent._memory[-1]["content"] == line


def test_the_user_side_is_not_normalised():
    """What the user typed is what they typed — including the script."""
    agent = _agent(TAIWAN)
    line = "我这边网络不太好"

    agent._add_message(line, "user")

    assert agent._memory[-1]["content"] == line


def test_okabe_chuuni_title_keeps_its_official_character():
    """「鳳凰院凶真」的「凶」會被 s2twp 轉成「兇」。

    跟紅莉栖的名字同一個坑：OpenCC 把專有名詞當一般詞彙做台灣用語轉換。
    這是岡部自封的稱號，官方寫法就是「凶真」。
    """
    from src.open_llm_vtuber.conversation_quality import (
        normalize_output_language_variant,
    )

    out = normalize_output_language_variant(
        "「鳳凰院兇真」就是岡部自己取的中二稱號。", "Traditional Chinese (Taiwan)"
    )
    assert "鳳凰院凶真" in out
    assert "兇真" not in out


def test_unrelated_xiong_is_left_alone():
    """只保護這個稱號，不是把所有的「兇」都改掉。"""
    from src.open_llm_vtuber.conversation_quality import (
        normalize_output_language_variant,
    )

    out = normalize_output_language_variant(
        "那傢伙的眼神有點兇。", "Traditional Chinese (Taiwan)"
    )
    assert "有點兇" in out
