"""直播的每一輪，她知道自己在直播、對面是觀眾。"""

import asyncio

import pytest

pytest.importorskip("ai_character_engine")

from src.open_llm_vtuber.conversation_quality import (  # noqa: E402
    STREAM_COMMENT_NOTE,
    STREAM_QUIET_NOTE,
)
from tests.test_engine_agent import EngineLLM, agent, companion, say  # noqa: E402


def _all_text(llm):
    # 主動開口可能多打一次（引擎的檢查），所以看這次對話裡所有的呼叫。
    return "\n".join(m.content for call in llm.calls for m in call)


def test_a_comment_turn_says_it_is_a_stream(tmp_path):
    llm = EngineLLM()
    current = agent(companion(tmp_path, llm))
    asyncio.run(
        say(
            current,
            "小明：今天好冷",
            stream=True,
            stream_comment={"author": "小明", "text": "今天好冷"},
        )
    )
    assert STREAM_COMMENT_NOTE in _all_text(llm)
    assert STREAM_QUIET_NOTE not in _all_text(llm)


def test_a_quiet_turn_says_it_is_a_stream(tmp_path):
    llm = EngineLLM()
    current = agent(companion(tmp_path, llm))
    asyncio.run(
        say(
            current, "（主動開口）", stream=True, proactive_speak=True, skip_memory=True
        )
    )
    assert STREAM_QUIET_NOTE in _all_text(llm)


def test_private_turns_have_no_stream_note(tmp_path):
    llm = EngineLLM()
    current = agent(companion(tmp_path, llm))
    asyncio.run(say(current, "今天好冷"))
    assert STREAM_COMMENT_NOTE not in _all_text(llm)
    assert STREAM_QUIET_NOTE not in _all_text(llm)
