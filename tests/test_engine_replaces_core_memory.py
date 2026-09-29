"""選了 character_engine_agent，「她記得對方什麼」由引擎負責。

core_memory.md 是主機自己的那一套：每幾輪用一次模型把整份重寫。引擎的記憶是逐條
的、帶出處的，而且背景工作會讓路給對話。兩套並存的時候，同一件事她會讀到兩次，
整理還多佔一次模型。她自己的記憶（self_memory.md）引擎沒有對應的東西，照舊。
"""

import asyncio

import pytest

from src.open_llm_vtuber import memory_core

pytest.importorskip("ai_character_engine")

from tests.test_engine_agent import (  # noqa: E402
    CONTEXT_MARK,
    EngineLLM,
    agent,
    companion,
    say,
)
from tests.test_memory_blocks_split import composed  # noqa: E402


def notes_of(llm, turn=-1):
    return "\n".join(m.content for m in llm.calls[turn] if CONTEXT_MARK in m.content)


def test_the_hosts_memory_of_the_user_is_no_longer_sent(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        current.set_system(composed("紅莉栖：喜歡胡椒博士。", "對方：住在台北。"))
        await say(current, "你好")
        return llm.calls[0][0].content, notes_of(llm)

    system, notes = asyncio.run(scenario())

    assert "台北" not in system + notes
    assert "紅莉栖：喜歡胡椒博士。" in notes


def test_what_the_host_remembered_before_is_handed_to_the_engine_once(
    tmp_path, monkeypatch
):
    """換 agent 之前累積的 core_memory.md 不能就這樣不見。只搬「對方」的那幾行；
    她自己說過什麼不是引擎記憶要記的事。搬過一次就不再搬：使用者之後在記憶頁
    刪掉的，重開之後不能又跑回來。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        memory_core,
        "load_core_memory",
        lambda conf_uid, history_uid: (
            "對方：名字是晨星。\nMao：罵對方是笨蛋。\n對方：養了一隻貓叫饅頭。"
        ),
    )

    async def scenario():
        first = agent(companion(tmp_path, EngineLLM()), conf_uid="kurisu")
        await say(first, "你好", history_uid="h1")
        imported = first.conversation_memory("h1")
        first.rewrite_conversation_memory("h1", "對方：名字是晨星。")

        restarted = agent(companion(tmp_path, EngineLLM()), conf_uid="kurisu")
        await say(restarted, "你好", history_uid="h1")
        return imported, restarted.conversation_memory("h1")

    imported, after_restart = asyncio.run(scenario())

    assert imported == "對方：名字是晨星。\n對方：養了一隻貓叫饅頭。"
    assert after_restart == "對方：名字是晨星。"


def test_the_memory_page_shows_and_edits_what_the_engine_remembers(tmp_path):
    async def scenario():
        llm = EngineLLM()
        current = agent(companion(tmp_path, llm))
        current.rewrite_conversation_memory("h1", "對方住在台北。\n\n對方養了一隻貓。")
        shown = current.conversation_memory("h1")
        await say(current, "你好", history_uid="h1")
        first = notes_of(llm)
        current.rewrite_conversation_memory("h1", "對方搬到台中了。")
        await say(current, "我搬家了", history_uid="h1")
        return shown, first, "".join(m.content for m in llm.calls[-1])

    shown, first, corrected = asyncio.run(scenario())

    assert shown == "對方住在台北。\n對方養了一隻貓。"
    assert "對方住在台北。" in first
    assert "台北" not in corrected
    assert "對方搬到台中了。" in corrected
