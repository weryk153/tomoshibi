"""直播中遊戲事件跟留言輪流；死亡優先；冷場先問遊戲。"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.stream.chat_source import ChatMessage
from src.open_llm_vtuber.stream.comment_picker import CommentPicker, PickerRules
from src.open_llm_vtuber.stream.session import StreamSession


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds
        await asyncio.sleep(0)


class HangingSource:
    connected = True

    async def messages(self):
        await asyncio.Event().wait()
        yield  # pragma: no cover

    async def close(self):
        pass


class Extra:
    def __init__(self):
        self.items = []

    def pick(self, now, *, urgent_only=False):
        for i, item in enumerate(self.items):
            if item.urgent or not urgent_only:
                return self.items.pop(i)
        return None


def item(name, urgent=False):
    return SimpleNamespace(name=name, urgent=urgent, notes=(name,))


def make(clock, extra, quiet_seconds=30):
    log = []

    async def run_turn(comment):
        log.append(("comment", comment.text) if comment else ("quiet", None))
        await clock.sleep(2)
        return "ok"

    async def run_extra(it):
        log.append(("game", it.name))
        await clock.sleep(2)
        return "ok"

    session = StreamSession(
        HangingSource(),
        CommentPicker(PickerRules(viewer_cooldown=0)),
        run_turn,
        quiet_seconds=quiet_seconds,
        failure_limit=3,
        clock=clock,
        sleep=clock.sleep,
        extra=extra,
        run_extra=run_extra,
    )
    session.stage_ready.set()
    return session, log


def comment(text):
    return ChatMessage(id=text, author="v" + text, text=text, timestamp=1000.0)


async def run_for(session, clock, seconds):
    task = asyncio.create_task(session.run())
    end = clock.now + seconds
    while clock.now < end:
        await clock.sleep(0.5)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def test_alternates_comment_and_game_and_death_first():
    clock = Clock()
    extra = Extra()
    session, log = make(clock, extra)
    for text in ("一", "二", "三"):
        session.picker.offer(comment(text), clock.now)
    extra.items = [item("night"), item("death", urgent=True)]
    asyncio.run(run_for(session, clock, 15))
    assert log[0] == ("game", "death")
    kinds = [kind for kind, _ in log[:5]]
    assert kinds == ["game", "comment", "game", "comment", "comment"]


def test_quiet_asks_game_before_speaking_on_its_own():
    clock = Clock()
    extra = Extra()
    session, log = make(clock, extra, quiet_seconds=5)
    extra.items = [item("idle")]
    asyncio.run(run_for(session, clock, 12))
    assert log[0] == ("game", "idle")
    assert ("quiet", None) in log


def test_extra_can_be_attached_and_detached_while_running():
    clock = Clock()
    session, log = make(clock, None, quiet_seconds=1000)
    extra = Extra()
    extra.items = [item("night")]

    async def go():
        task = asyncio.create_task(session.run())
        await clock.sleep(1)
        session.extra = extra
        await clock.sleep(3)
        session.extra = None
        extra.items = [item("never")]
        await clock.sleep(3)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(go())
    assert log == [("game", "night")]


def test_peek_does_not_consume():
    picker = CommentPicker(PickerRules(viewer_cooldown=0))
    picker.offer(comment("一"), 1000.0)
    assert picker.peek(1001.0).text == "一"
    assert picker.pick(1001.0).text == "一"
    assert picker.peek(1002.0) is None
