"""「她記得對方什麼」「她自己的事」都由引擎負責。

core_memory.md、self_memory.md 是 Tomoshibi 以前自己的那一套。那一套已經拿掉，
留下的舊檔案也不搬進引擎。
"""

import asyncio

import pytest


pytest.importorskip("ai_character_engine")

from tests.test_engine_agent import (  # noqa: E402
    CONTEXT_MARK,
    EngineLLM,
    agent,
    companion,
    say,
)


def notes_of(llm, turn=-1):
    return "\n".join(m.content for m in llm.calls[turn] if CONTEXT_MARK in m.content)


def test_old_memory_files_are_not_brought_into_the_engine(tmp_path, monkeypatch):
    """舊 agent 留下的 core_memory.md、self_memory.md 不搬進引擎。

    實機：芙莉蓮的 self_memory.md 是舊整理把她當下說的話（「現在凌晨兩點半，去遠方
    不太方便」）記成事實；搬進引擎之後每一輪都帶著，她回「嗨」也在講不方便出遠門。
    """
    monkeypatch.chdir(tmp_path)
    old_dir = tmp_path / "chat_history" / "kurisu"
    (old_dir / "h1").mkdir(parents=True)
    (old_dir / "self_memory.md").write_text(
        "紅莉栖：現在凌晨兩點半。", encoding="utf-8"
    )
    (old_dir / "h1" / "core_memory.md").write_text(
        "對方：名字是晨星。\n紅莉栖：喜歡胡椒博士。", encoding="utf-8"
    )

    async def scenario():
        current = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        shown_first = current.self_memory()
        await say(current, "你好", history_uid="h1")
        return shown_first, current.self_memory(), current.conversation_memory("h1")

    assert asyncio.run(scenario()) == ("", "", "")


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


def test_saving_the_page_keeps_what_arrived_while_it_was_open(tmp_path):
    async def scenario():
        engine = companion(tmp_path, EngineLLM())
        current = agent(engine)
        current.rewrite_conversation_memory("h1", "對方：住在台北。")
        shown = current.conversation_memory("h1")
        engine.rewrite_memories("h1", ["對方：住在台北。", "對方：養了一隻貓。"])
        current.rewrite_conversation_memory(
            "h1", "對方：住在台北。\n對方：喜歡烏龍茶。", edited_from=shown
        )
        return current.conversation_memory("h1")

    assert (
        asyncio.run(scenario())
        == "對方：住在台北。\n對方：養了一隻貓。\n對方：喜歡烏龍茶。"
    )


def test_interrupting_a_reply_that_is_being_played_finds_its_own_conversation(tmp_path):
    """A 的回覆已經生成完、正在播；B 接著講完一句。A 那邊打斷：主機取消 A 那一輪
    的 task（播放期間它還活著），再呼叫 handle_interrupt。"""

    async def scenario():
        llm = EngineLLM("嗯，我知道了。")
        engine = companion(tmp_path, llm)
        current = agent(engine)
        playing = asyncio.Event()

        async def a_turn():
            outputs = await say(current, "我是A", history_uid="h1")
            await playing.wait()  # the host's turn lives on while audio plays
            return outputs

        a = asyncio.ensure_future(a_turn())
        for _ in range(50):
            await asyncio.sleep(0)
        await say(current, "我是B", history_uid="h2")
        a.cancel()
        current.handle_interrupt("嗯")
        with pytest.raises(asyncio.CancelledError):
            await a
        await say(current, "繼續", history_uid="h1")
        in_a = llm.said_by_both()
        await say(current, "繼續", history_uid="h2")
        return in_a, llm.said_by_both()

    in_a, in_b = asyncio.run(scenario())

    assert in_a == ["我是A", "嗯 [Interrupted by user]", "繼續"]
    assert in_b == ["我是B", "嗯，我知道了。", "繼續"]
