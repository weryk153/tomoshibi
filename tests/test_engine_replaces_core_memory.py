"""「她記得對方什麼」「她自己的事」都由引擎負責。

core_memory.md、self_memory.md 是 Tomoshibi 以前自己的那一套。那一套已經拿掉，
留下的舊檔案由引擎匯入一次。
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


def write_old_self_memory(conf_uid, text):
    """Tomoshibi 以前自己存的 self_memory.md；現在只剩引擎匯入時讀它。"""
    path = memory_core._self_memory_file(conf_uid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def notes_of(llm, turn=-1):
    return "\n".join(m.content for m in llm.calls[turn] if CONTEXT_MARK in m.content)


def test_what_the_host_remembered_before_is_handed_to_the_engine_once(
    tmp_path, monkeypatch
):
    """換 agent 之前累積的 core_memory.md 不能就這樣不見。「對方」的那幾行進這段
    對話的記憶，她自己的那幾行進她自己的記憶。搬過一次就不再搬：使用者之後在
    記憶頁刪掉的，重開之後不能又跑回來。"""
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
        her_own = first.self_memory()
        first.rewrite_conversation_memory("h1", "對方：名字是晨星。")

        restarted = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(restarted, "你好", history_uid="h1")
        return imported, her_own, restarted.conversation_memory("h1")

    imported, her_own, after_restart = asyncio.run(scenario())

    assert imported == (
        "對方：名字是晨星。\n對方對貓過敏。\n對方 下週要去京都出差三天。\n養了一隻貓叫饅頭。"
    )
    assert after_restart == "對方：名字是晨星。"
    # 她自己的那幾行不是丟掉，是進她自己的記憶（舊檔案裡有從沒搬去那邊的）。
    assert her_own == "紅莉栖：喜歡胡椒博士。"
    assert memory_core.read_self_memory("kurisu") == ""


def test_what_she_remembered_of_herself_before_is_handed_to_the_engine_once(
    tmp_path, monkeypatch
):
    """self_memory.md 是她在所有對話裡說過自己的事。換 agent 之後搬進引擎一次；
    使用者之後在記憶頁刪掉的，重開之後不能又跑回來。"""
    monkeypatch.chdir(tmp_path)
    write_old_self_memory("kurisu", "紅莉栖：在學鋼琴。\n紅莉栖：喜歡胡椒博士。")

    async def scenario():
        first = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(first, "你好", history_uid="h1")
        imported = first.self_memory()
        first.rewrite_self_memory("紅莉栖：在學鋼琴。")

        restarted = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(restarted, "你好", history_uid="h2")
        return imported, restarted.self_memory()

    imported, after_restart = asyncio.run(scenario())

    assert imported == "紅莉栖：在學鋼琴。\n紅莉栖：喜歡胡椒博士。"
    assert after_restart == "紅莉栖：在學鋼琴。"


def test_an_unreadable_self_memory_is_brought_over_once_it_can_be_read(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    write_old_self_memory("kurisu", "紅莉栖：喜歡胡椒博士。")
    readable = memory_core.read_self_memory

    def unreadable(conf_uid):
        raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad")

    async def scenario():
        monkeypatch.setattr(memory_core, "read_self_memory", unreadable)
        first = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(first, "你好", history_uid="h1")
        before = first.self_memory()
        monkeypatch.setattr(memory_core, "read_self_memory", readable)
        later = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        await say(later, "你好", history_uid="h1")
        return before, later.self_memory()

    assert asyncio.run(scenario()) == ("", "紅莉栖：喜歡胡椒博士。")


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


def test_what_she_said_before_the_engine_kept_it_counts_as_her_oldest(
    tmp_path, monkeypatch
):
    """每段舊對話第一次打開，都會把它 core_memory.md 裡她自己的那幾行搬進來。當成
    最新的話，搬幾段之後她最近說的會被擠出去。"""
    monkeypatch.chdir(tmp_path)
    write_old_self_memory("kurisu", "紅莉栖：以前說過的。")

    async def scenario():
        engine = companion(tmp_path, EngineLLM())
        engine.rewrite_self_memories(["紅莉栖剛剛說她在學鋼琴。"])
        current = agent(engine, conf_uid="kurisu", character_name="紅莉栖")
        await say(current, "你好", history_uid="h1")
        return engine.self_memories()

    assert asyncio.run(scenario()) == [
        "紅莉栖：以前說過的。",
        "紅莉栖剛剛說她在學鋼琴。",
    ]


def test_the_memory_page_before_her_first_word_shows_what_she_remembers(
    tmp_path, monkeypatch
):
    """記憶頁在她開口之前打開：以前顯示空的，清掉之後第一輪又把舊檔案搬回來。"""
    monkeypatch.chdir(tmp_path)
    write_old_self_memory("kurisu", "紅莉栖：在學鋼琴。")

    async def scenario():
        current = agent(
            companion(tmp_path, EngineLLM()), conf_uid="kurisu", character_name="紅莉栖"
        )
        shown = current.self_memory()
        current.rewrite_self_memory("")
        await say(current, "你好", history_uid="h1")
        return shown, current.self_memory()

    assert asyncio.run(scenario()) == ("紅莉栖：在學鋼琴。", "")
