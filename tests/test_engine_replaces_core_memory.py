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
    # 真實的 core_memory.md 不只一種寫法：審查在本機的檔案裡數過，30 行關於對方的
    # 有 20 行不是「對方：」開頭。分法沿用主機自己的 classify_memory_lines。
    monkeypatch.setattr(
        memory_core,
        "load_core_memory",
        lambda conf_uid, history_uid: (
            "對方：名字是晨星。\n紅莉栖：喜歡胡椒博士。\n- 對方對貓過敏。\n"
            "對方 下週要去京都出差三天。\n1. 養了一隻貓叫饅頭。"
        ),
    )

    async def scenario():
        first = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(first, "你好", history_uid="h1")
        imported = first.conversation_memory("h1")
        first.rewrite_conversation_memory("h1", "對方：名字是晨星。")

        restarted = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(restarted, "你好", history_uid="h1")
        return imported, restarted.conversation_memory("h1")

    imported, after_restart = asyncio.run(scenario())

    assert imported == (
        "對方：名字是晨星。\n對方對貓過敏。\n對方 下週要去京都出差三天。\n養了一隻貓叫饅頭。"
    )
    assert after_restart == "對方：名字是晨星。"
    # 她自己的那幾行不是丟掉，是併進她自己的記憶（舊檔案裡有從沒搬去那邊的）。
    assert "紅莉栖：喜歡胡椒博士。" in memory_core.load_self_memory("kurisu")


def test_her_lines_from_an_old_conversation_do_not_outrank_what_she_knows_now(
    tmp_path, monkeypatch
):
    """舊 core_memory.md 裡她自己的那幾行比 self_memory.md 現在的內容舊。相近的
    兩行要留現在的；裝不下的時候先丟舊檔案帶來的，不是現在的。"""
    monkeypatch.chdir(tmp_path)
    memory_core.save_self_memory(
        "kurisu", "紅莉栖：每天早上都要先喝一杯紅茶才開始工作。\n紅莉栖：在學鋼琴。"
    )
    monkeypatch.setattr(
        memory_core,
        "load_core_memory",
        lambda conf_uid,
        history_uid: "紅莉栖：每天早上都要先喝一杯咖啡才開始工作。\n紅莉栖：喜歡胡椒博士。",
    )

    async def scenario():
        current = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(current, "你好", history_uid="h1")

    asyncio.run(scenario())

    own = memory_core.load_self_memory("kurisu").splitlines()
    assert "紅莉栖：每天早上都要先喝一杯紅茶才開始工作。" in own
    assert "紅莉栖：每天早上都要先喝一杯咖啡才開始工作。" not in own
    assert "紅莉栖：在學鋼琴。" in own
    assert "紅莉栖：喜歡胡椒博士。" in own


def test_a_migration_that_could_not_save_her_lines_is_tried_again(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        memory_core,
        "load_core_memory",
        lambda conf_uid, history_uid: "對方：名字是晨星。\n紅莉栖：喜歡胡椒博士。",
    )
    saves = []

    def failing_save(conf_uid, content):
        saves.append(content)
        return len(saves) > 1

    monkeypatch.setattr(memory_core, "save_self_memory", failing_save)

    async def scenario():
        first = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(first, "你好", history_uid="h1")
        second = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(second, "你好", history_uid="h1")

    asyncio.run(scenario())

    assert len(saves) == 2
    assert all("紅莉栖：喜歡胡椒博士。" in content for content in saves)


def test_an_unreadable_self_memory_is_not_overwritten_by_the_migration(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        memory_core,
        "load_core_memory",
        lambda conf_uid, history_uid: "紅莉栖：喜歡胡椒博士。",
    )

    def unreadable(conf_uid):
        raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad")

    monkeypatch.setattr(memory_core, "read_self_memory", unreadable)
    saves = []
    monkeypatch.setattr(
        memory_core, "save_self_memory", lambda conf_uid, content: saves.append(content)
    )

    async def scenario():
        current = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(current, "你好", history_uid="h1")

    asyncio.run(scenario())

    assert saves == []
    assert not (
        tmp_path / "chat_history" / "kurisu" / "engine" / "brought-from-core-memory.txt"
    ).exists()


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
