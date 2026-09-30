"""主機的長期記憶（core_memory.md、self_memory.md）怎麼到她那裡。

主機把記憶寫在系統提示的中段，而記憶每一輪都會被整理一次。LM Studio 的紀錄：
每一輪都只有 cached_tokens=2048，後面 2300～3400 個 token 連同整段對話全部重讀，
兩種 agent 都一樣。character_engine_agent 把記憶從系統提示裡拿出來、交給引擎寫進
對話的備註，系統提示就不會再跟著記憶變。
"""

import asyncio

import pytest

pytest.importorskip("ai_character_engine")

from datetime import datetime  # noqa: E402

from src.open_llm_vtuber.conversation_quality import (  # noqa: E402
    CORE_CONVERSATION_PROMPT,
)
from tests.test_engine_agent import (  # noqa: E402
    CONTEXT_MARK,
    EngineLLM,
    agent,
    companion,
    say,
)
from tests.test_memory_blocks_split import composed  # noqa: E402


def test_her_own_memory_arrives_as_notes_and_the_persona_stays_the_same(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        current.set_system(composed("紅莉栖：喜歡胡椒博士。", ""))
        await say(current, "你好")
        # 每一輪之後記憶都會被整理一次，主機接著重組系統提示。
        current.set_system(composed("紅莉栖：喜歡胡椒博士。\n紅莉栖：怕蟑螂。", ""))
        await say(current, "還記得我嗎")
        return llm.calls

    first, second = asyncio.run(scenario())

    assert first[0] == second[0]
    assert "胡椒博士" not in first[0].content
    assert CORE_CONVERSATION_PROMPT in first[0].content
    assert second[: len(first)] == first

    (first_note,) = [m.content for m in first if CONTEXT_MARK in m.content]
    assert "- 你對自己的認知：紅莉栖：喜歡胡椒博士。" in first_note

    new_note = [m.content for m in second if CONTEXT_MARK in m.content][-1]
    assert "- 你對自己的認知：紅莉栖：怕蟑螂。" in new_note
    assert "胡椒博士" not in new_note


def test_what_she_no_longer_knows_of_herself_is_no_longer_sent(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        current.set_system(composed("紅莉栖：住在秋葉原。", ""))
        await say(current, "你好")
        current.set_system(composed("紅莉栖：搬到池袋了。", ""))
        await say(current, "你搬家了")
        corrected = "".join(llm.sent())
        current.set_system(composed("", ""))
        await say(current, "忘了吧")
        return corrected, "".join(llm.sent())

    corrected, cleared = asyncio.run(scenario())

    assert "秋葉原" not in corrected
    assert "搬到池袋了" in corrected
    assert "池袋" not in cleared


def test_how_to_use_the_memory_is_still_said(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        current.set_system(composed("紅莉栖：喜歡胡椒博士。", ""))
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
