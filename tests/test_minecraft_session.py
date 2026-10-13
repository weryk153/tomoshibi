"""Minecraft 模式的迴圈：狀態進來變事件、閒了問她、直播中讓位、連續失敗就停。"""

import asyncio

from src.open_llm_vtuber.minecraft.events import EventRules, GameState
from src.open_llm_vtuber.minecraft.feed import FeedRules, GameFeed
from src.open_llm_vtuber.minecraft.session import MinecraftSession


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds
        await asyncio.sleep(0)


def state(health=20, idle=True, action="Idle"):
    return {
        "gameplay": {"health": health},
        "action": {"current": action, "isIdle": idle},
    }


def make(clock, results=(), live=lambda: False, failure_limit=3, ready=lambda: True):
    turns = []
    results = list(results)

    async def run_turn(turn):
        turns.append(turn)
        await clock.sleep(1)
        return results.pop(0) if results else "ok"

    feed = GameFeed(FeedRules(idle_seconds=5, idle_cooldown=10, event_cooldown=0))
    session = MinecraftSession(
        feed,
        run_turn,
        rules=EventRules(notable_items=("diamond",)),
        stream_live=live,
        failure_limit=failure_limit,
        clock=clock,
        sleep=clock.sleep,
    )
    feed.ready = ready
    return session, turns


async def tick(session, clock, seconds, state_fn=None):
    for _ in range(int(seconds * 2)):
        if state_fn:
            session.handle_state(state_fn())
        await clock.sleep(0.5)


def test_death_becomes_an_urgent_turn():
    clock = Clock()
    session, turns = make(clock)

    async def go():
        task = asyncio.create_task(session.run())
        session.handle_state(state(health=5, idle=False, action="dig"))
        session.handle_state(state(health=0, idle=False, action="dig"))
        await tick(session, clock, 2)
        task.cancel()

    asyncio.run(go())
    assert turns and turns[0].urgent and "死掉" in turns[0].notes[0]


def test_idle_turn_and_report_event():
    clock = Clock()
    session, turns = make(clock)

    async def go():
        task = asyncio.create_task(session.run())
        await tick(session, clock, 6, lambda: state())
        session.handle_output("I built a shelter.")
        await tick(session, clock, 2)
        task.cancel()

    asyncio.run(go())
    kinds = [t.kind for t in turns]
    assert kinds[0] == "idle"
    assert any("I built a shelter." in "\n".join(t.notes) for t in turns)


def test_waits_while_stream_is_live():
    clock = Clock()
    live = {"on": True}
    session, turns = make(clock, live=lambda: live["on"])

    async def go():
        task = asyncio.create_task(session.run())
        await tick(session, clock, 8, lambda: state())
        assert turns == []
        live["on"] = False
        await tick(session, clock, 2, lambda: state())
        task.cancel()

    asyncio.run(go())
    assert [t.kind for t in turns] == ["idle"]


def test_disconnect_once_and_failures_stop():
    clock = Clock()
    session, turns = make(clock, results=["failed", "failed"], failure_limit=2)

    async def go():
        task = asyncio.create_task(session.run())
        session.handle_disconnect()
        session.handle_disconnect()
        await tick(session, clock, 2)
        session.handle_output("x")
        await tick(session, clock, 2)
        return await task

    assert asyncio.run(go()) == "failures"
    assert len([t for t in turns if "連線" in t.notes[0]]) == 1


def test_no_idle_turns_after_disconnect_until_ready_again():
    clock = Clock()
    ready = {"on": True}
    session, turns = make(clock, ready=lambda: ready["on"])

    async def go():
        task = asyncio.create_task(session.run())
        session.handle_state(state())
        session.handle_disconnect()
        ready["on"] = False
        await tick(session, clock, 60, state)
        # 斷線事件本身會講一輪，之後不該再有閒置輪
        assert [t.kind for t in turns] == ["event"]
        ready["on"] = True
        await tick(session, clock, 20, state)
        task.cancel()

    asyncio.run(go())
    assert "idle" in [t.kind for t in turns[1:]]


def test_malformed_state_creates_no_events():
    clock = Clock()
    session, _ = make(clock)
    session.handle_state(state(health=5, idle=False))
    session.handle_state({"error": "x"})
    session.handle_state("junk")
    session.handle_state({"action": {}})
    assert session.latest is not None and session.latest.health == 5
    session.handle_state(state(health=5, idle=False))
    assert session.feed.pending() == 0


def test_turn_that_returns_without_awaiting_does_not_spin_the_loop():
    """沒有視窗時 run_private_turn 立刻回 interrupted、不 await；cooldown 設 0 的話
    迴圈一輪都不讓出事件迴圈，整個 server 會卡住。每輪結束都要睡一下。"""
    clock = Clock()
    turns = []

    async def run_turn(turn):
        turns.append(turn)
        return "interrupted"

    feed = GameFeed(FeedRules(idle_seconds=1, idle_cooldown=0, event_cooldown=0))
    session = MinecraftSession(
        feed,
        run_turn,
        rules=EventRules(),
        stream_live=lambda: False,
        failure_limit=3,
        clock=clock,
        sleep=clock.sleep,
    )

    async def go():
        task = asyncio.create_task(session.run())
        feed.observe(GameState(), 0)
        clock.now = 1
        for _ in range(20):
            await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(go())
    # 二十次讓出事件迴圈，若每輪都睡一下（假時鐘每次推進 0.5 秒），回合數一定有限且時間有前進。
    assert 0 < len(turns) <= 20
    assert clock.now > 1
