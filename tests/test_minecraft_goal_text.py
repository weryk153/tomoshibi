"""她在台詞裡寫的 [minecraft_do: ...] 要抓出來送給身體，講話裡拿掉。"""

import asyncio

from src.open_llm_vtuber.minecraft import goal_text
from src.open_llm_vtuber.minecraft.goal_text import extract_goals


def test_bracket_form_is_extracted_and_removed():
    clean, goals = extract_goals("[minecraft_do: collect 10 oak logs] 先把木頭收齊。")
    assert goals == ["collect 10 oak logs"]
    assert clean == "先把木頭收齊。"


def test_other_spellings():
    assert extract_goals('minecraft_do: "build a shelter"')[1] == ["build a shelter"]
    assert extract_goals('[minecraft_do("go mine iron")]')[1] == ["go mine iron"]
    assert extract_goals("MINECRAFT_DO：craft a stone pickaxe")[1] == [
        "craft a stone pickaxe"
    ]


def test_plain_sentence_untouched():
    clean, goals = extract_goals("我先去找點木頭。")
    assert goals == [] and clean == "我先去找點木頭。"


def test_tag_only_sentence_becomes_empty():
    clean, goals = extract_goals("[minecraft_do: collect wood]")
    assert goals == ["collect wood"] and clean == ""


def test_dispatch_sends_through_sink_and_is_quiet_without_one():
    goal_text._recent.clear()
    sent = []

    async def sink(goal):
        sent.append(goal)

    async def go():
        goal_text.sink = sink
        goal_text.dispatch(["collect wood", "craft planks"])
        await asyncio.sleep(0)
        goal_text.sink = None
        goal_text.dispatch(["ignored"])
        await asyncio.sleep(0)

    asyncio.run(go())
    assert sent == ["collect wood", "craft planks"]


def test_same_goal_is_not_resent_within_the_window():
    goal_text._recent.clear()
    sent = []

    async def sink(goal):
        sent.append(goal)

    async def go():
        goal_text.sink = sink
        goal_text.dispatch(["collect 10 oak logs"])
        goal_text.dispatch(["Collect 10 oak logs", "craft a crafting table"])
        await asyncio.sleep(0)
        goal_text.sink = None

    asyncio.run(go())
    assert sent == ["collect 10 oak logs", "craft a crafting table"]


def test_pending_dispatch_does_not_cross_a_mode_restart():
    goal_text._recent.clear()
    sent = []

    async def old(goal):
        sent.append(("old", goal))

    async def new(goal):
        sent.append(("new", goal))

    async def go():
        goal_text.sink = old
        goal_text.dispatch(["collect 10 oak logs"])
        goal_text.sink = new
        await asyncio.sleep(0)
        goal_text.sink = None

    asyncio.run(go())
    assert sent == []
