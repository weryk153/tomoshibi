"""她知道這段對話是直播：開播時說一次，記在這場直播的對話裡，不是每一輪都塞一次。"""

import asyncio

import pytest

pytest.importorskip("ai_character_engine")

from src.open_llm_vtuber.conversation_quality import STREAM_FACT  # noqa: E402
from tests.test_engine_agent import EngineLLM, agent, companion, say  # noqa: E402


def _last_call(llm):
    return "\n".join(m.content for m in llm.calls[-1])


def _all_calls(llm):
    return "\n".join(m.content for call in llm.calls for m in call)


def test_the_stream_fact_is_said_once_and_kept(tmp_path):
    llm = EngineLLM()
    current = agent(companion(tmp_path, llm))

    async def scenario():
        for text in ("小明：今天好冷", "阿華：妳好"):
            await say(current, text, stream=True, history_uid="stream-1")

    asyncio.run(scenario())
    last = _last_call(llm)
    assert last.count(STREAM_FACT) == 1
    assert f"For the next reply only: {STREAM_FACT}" not in last


def test_a_quiet_turn_knows_it_is_a_stream(tmp_path):
    llm = EngineLLM()
    current = agent(companion(tmp_path, llm))
    asyncio.run(
        say(
            current,
            "（主動開口）",
            stream=True,
            proactive_speak=True,
            skip_memory=True,
            history_uid="stream-1",
        )
    )
    assert STREAM_FACT in _all_calls(llm)


def test_private_turns_do_not_hear_about_the_stream(tmp_path):
    llm = EngineLLM()
    current = agent(companion(tmp_path, llm))
    asyncio.run(say(current, "今天好冷"))
    assert STREAM_FACT not in _all_calls(llm)
