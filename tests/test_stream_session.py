"""一次一則、冷場開口、直播結束、連續失敗、斷線重試、等舞台。"""

import asyncio

import pytest

from src.open_llm_vtuber.stream.chat_source import ChatMessage, ChatSourceError
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


class ScriptedSource:
    """依序跑 attempts：每個 attempt 是 (留言文字們, 結尾)；結尾 end／error／hang。"""

    def __init__(self, clock, attempts):
        self.clock = clock
        self.attempts = list(attempts)
        self.connected = False
        self.closed = False

    async def messages(self):
        texts, ending = self.attempts.pop(0)
        self.connected = True
        for i, text in enumerate(texts):
            await self.clock.sleep(1)
            yield ChatMessage(
                id=text, author=f"v{i}-{text}", text=text, timestamp=self.clock()
            )
        if ending == "error":
            self.connected = False
            raise ChatSourceError("boom")
        if ending == "hang":
            await asyncio.Event().wait()

    async def close(self):
        self.closed = True


def make(clock, source, results, **options):
    turns = []
    running = []

    async def run_turn(comment):
        assert not running, "two turns at once"
        running.append(1)
        turns.append(None if comment is None else comment.text)
        await clock.sleep(2)
        running.pop()
        return results.pop(0) if results else "ok"

    session = StreamSession(
        source,
        CommentPicker(PickerRules(viewer_cooldown=0)),
        run_turn,
        quiet_seconds=options.pop("quiet_seconds", 30),
        failure_limit=options.pop("failure_limit", 3),
        clock=clock,
        sleep=clock.sleep,
        **options,
    )
    session.stage_ready.set()
    return session, turns


def test_answers_comments_one_at_a_time_then_ends():
    clock = Clock()
    source = ScriptedSource(clock, [(["一", "二", "三"], "end")])
    session, turns = make(clock, source, [])
    assert asyncio.run(session.run()) == "ended"
    # 留言一則一則進來、她一則一則回，順序看讀與回怎麼交錯；要的是三則都回到、一次一則。
    assert set(turns) == {"一", "二", "三"}
    assert len(turns) == 3
    assert session.chat_status() == "ended"
    assert source.closed


def test_quiet_chat_gets_a_proactive_turn():
    clock = Clock()
    source = ScriptedSource(clock, [([], "hang")])
    session, turns = make(clock, source, [], quiet_seconds=30)

    async def run():
        task = asyncio.create_task(session.run())
        while not turns:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert turns[0] is None
    assert source.closed


def test_failures_in_a_row_stop_the_session_and_ok_resets():
    clock = Clock()
    source = ScriptedSource(clock, [(["a", "b", "c", "d", "e"], "hang")])
    session, turns = make(
        clock, source, ["failed", "ok", "failed", "failed"], failure_limit=2
    )
    assert asyncio.run(session.run()) == "failures"
    assert len(turns) == 4


def test_interrupted_turns_are_not_failures():
    clock = Clock()
    source = ScriptedSource(clock, [(["a", "b", "c"], "end")])
    session, turns = make(clock, source, ["interrupted"] * 3, failure_limit=1)
    assert asyncio.run(session.run()) == "ended"
    assert len(turns) == 3


def test_chat_errors_retry_with_backoff():
    clock = Clock()
    source = ScriptedSource(clock, [([], "error"), ([], "error"), (["好"], "end")])
    session, turns = make(clock, source, [], backoff=(5.0, 10.0))
    start = clock.now
    assert asyncio.run(session.run()) == "ended"
    assert turns == ["好"]
    assert session.last_error == "boom"
    assert clock.now - start >= 15


def test_nothing_runs_while_the_stage_is_away():
    clock = Clock()
    source = ScriptedSource(clock, [(["一"], "hang")])
    session, turns = make(clock, source, [])
    session.stage_ready.clear()

    async def run():
        task = asyncio.create_task(session.run())
        for _ in range(50):
            await asyncio.sleep(0)
        assert turns == []
        assert len(session.picker) == 1
        session.stage_ready.set()
        while not turns:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert turns == ["一"]


def test_an_unexpected_reader_error_is_retried_not_swallowed():
    """讀聊天室遇到非預期的例外（YouTube 改版）不能默默死掉、畫面還顯示已連上。"""
    clock = Clock()

    class Flaky(ScriptedSource):
        async def messages(self):
            if not self.attempts[0][0]:
                self.attempts.pop(0)
                raise AttributeError("'list' object has no attribute 'get'")
            async for message in super().messages():
                yield message

    source = Flaky(clock, [([], "error"), (["好"], "end")])
    session, turns = make(clock, source, [], backoff=(5.0,))
    assert asyncio.run(session.run()) == "ended"
    assert turns == ["好"]
    assert "AttributeError" in session.last_error
