"""她記得什麼怎麼到她那裡。

記憶不放在系統提示裡：記憶每一輪都會變，放在系統提示中段會讓 LM Studio 的快取
每輪從那裡重讀。她記得對方什麼、她自己說過什麼，都由引擎記、由引擎寫進對話的
備註，系統提示只放人設與怎麼用記憶。
"""

import asyncio

import pytest

pytest.importorskip("ai_character_engine")

from datetime import datetime  # noqa: E402

from tests.test_engine_agent import (  # noqa: E402
    CONTEXT_MARK,
    EngineLLM,
    agent,
    companion,
    say,
)


def test_her_own_memory_comes_from_the_engine(tmp_path):
    async def scenario():
        llm = EngineLLM()
        engine = companion(tmp_path, llm)
        current = agent(engine)
        engine.rewrite_self_memories(["紅莉栖喜歡胡椒博士。"])
        await say(current, "你好")
        return [m.content for m in llm.calls[0] if CONTEXT_MARK in m.content]

    (note,) = asyncio.run(scenario())

    assert "紅莉栖喜歡胡椒博士。" in note


def test_how_to_use_the_memory_is_still_said(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        current.set_system("你是紅莉栖。")
        await say(current, "你好")
        return llm.calls[0][0].content

    assert "自然運用、不要生硬複述" in asyncio.run(scenario())


def test_she_knows_what_time_it_is(tmp_path):
    """問她現在幾點，9B 的模型有一半的機會不呼叫時間工具、自己編一個時間
    （實測 6 次裡 3 次，提醒放多近都一樣）。"""
    clock = iter([datetime(2026, 9, 29, 3, 45), datetime(2026, 9, 29, 3, 47)])

    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm), now=lambda: next(clock))
        await say(current, "現在幾點")
        await say(current, "那現在呢")
        return [m.content for m in llm.calls[-1] if CONTEXT_MARK in m.content]

    first, second = asyncio.run(scenario())

    assert "For the next reply only: 現在時間：2026-09-29（週二）03:45" in first
    assert "03:45" not in second
    assert "For the next reply only: 現在時間：2026-09-29（週二）03:47" in second
