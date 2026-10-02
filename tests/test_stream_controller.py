"""開始前要有舞台與網址；停止會收乾淨；舞台斷線只是暫停。"""

import asyncio

import pytest

from src.open_llm_vtuber.config_manager.stream import StreamConfig
from src.open_llm_vtuber.stream.chat_source import ChatMessage
from src.open_llm_vtuber.stream.controller import StreamController, StreamError


class FakeSource:
    def __init__(self, texts=(), hang=True):
        self.texts = list(texts)
        self.hang = hang
        self.connected = True

    async def messages(self):
        for i, text in enumerate(self.texts):
            yield ChatMessage(id=str(i), author=f"v{i}", text=text, timestamp=0.0)
        if self.hang:
            await asyncio.Event().wait()

    async def close(self):
        pass


class FakeHost:
    def __init__(self):
        self.histories = 0
        self.live_events = []
        self.stopped_audio = []
        self.turns = []
        self.block = asyncio.Event()

    def new_stream_history(self, stage_uid):
        self.histories += 1
        return f"stream-{self.histories}"

    def character_names(self, stage_uid):
        return ("芙莉蓮",)

    def turn_runner(self, history_uid):
        async def run(comment):
            self.turns.append((history_uid, None if comment is None else comment.text))
            await self.block.wait()
            return "ok"

        return run

    async def live_changed(self, live):
        self.live_events.append(live)

    async def stop_stage_audio(self, stage_uid):
        self.stopped_audio.append(stage_uid)


def controller(host, source=None, settings=None):
    saved = {}
    current = settings or StreamConfig(youtube_url="https://youtu.be/abcdefghijk")

    def write(changes):
        saved.update(changes)
        return current.model_copy(update=changes)

    c = StreamController(
        host,
        open_source=lambda url: source or FakeSource(),
        read_settings=lambda: current,
        write_settings=write,
        # 時間停在 0、sleep 不真的等：沒有留言時講話迴圈只是讓出控制權，測試不用等真的秒數。
        session_options={"clock": lambda: 0.0, "sleep": lambda s: asyncio.sleep(0)},
    )
    c.saved = saved
    return c


async def _until(predicate):
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never became true")


def _bad_url(url):
    raise ValueError("bad")


def test_start_needs_a_stage_and_a_url():
    async def run():
        host = FakeHost()
        c = controller(host, settings=StreamConfig())
        with pytest.raises(StreamError) as no_stage:
            await c.start()
        c.attach_stage("stage-1")
        with pytest.raises(StreamError) as no_url:
            await c.start()
        c2 = controller(host)
        c2._open_source = _bad_url
        c2.attach_stage("stage-1")
        with pytest.raises(StreamError) as bad_url:
            await c2.start("https://www.youtube.com/@x/live")
        return no_stage.value.reason, no_url.value.reason, bad_url.value.reason

    assert asyncio.run(run()) == ("no_stage", "no_url", "bad_url")


def test_start_runs_turns_and_stop_cleans_up():
    async def run():
        host = FakeHost()
        c = controller(host, FakeSource(["芙莉蓮妳好"]))
        c.attach_stage("stage-1")
        status = await c.start("https://youtu.be/zyxwvutsrqp")
        assert status["live"] is True
        assert c.saved == {"youtube_url": "https://youtu.be/zyxwvutsrqp"}
        await _until(lambda: host.turns)
        assert c.status()["current"] == {"author": "v0", "text": "芙莉蓮妳好"}
        with pytest.raises(StreamError) as again:
            await c.start()
        stopped = await c.stop()
        return host, stopped, again.value.reason

    host, stopped, again = asyncio.run(run())
    assert again == "already_live"
    assert host.turns == [("stream-1", "芙莉蓮妳好")]
    assert stopped["live"] is False
    assert stopped["stopped_reason"] == "stopped"
    assert stopped["current"] is None
    assert host.live_events == [True, False]
    assert host.stopped_audio == ["stage-1"]


def test_the_stream_ending_stops_by_itself():
    async def run():
        host = FakeHost()
        host.block.set()
        c = controller(host, FakeSource(["嗨"], hang=False))
        c.attach_stage("stage-1")
        await c.start()
        await _until(lambda: not c.live)
        return c.status(), host

    status, host = asyncio.run(run())
    assert status["stopped_reason"] == "ended"
    assert host.live_events == [True, False]


def test_a_new_stage_replaces_the_old_one_and_detach_pauses():
    async def run():
        host = FakeHost()
        c = controller(host)
        assert c.attach_stage("stage-1") is None
        assert c.attach_stage("stage-2") == "stage-1"
        assert c.attach_stage("stage-2") is None
        await c.start()
        c.detach_stage("stage-1")  # 舊的走了不影響
        assert c.status()["stage_connected"] is True
        c.detach_stage("stage-2")
        status = c.status()
        await c.stop()
        return status

    status = asyncio.run(run())
    assert status["live"] is True
    assert status["stage_connected"] is False


def test_after_failures_start_continues_the_same_conversation():
    async def run():
        host = FakeHost()
        c = controller(host)
        c.attach_stage("stage-1")
        await c.start()
        first = c.status()["history_uid"]
        await c.stop()
        c.stopped_reason = "failures"  # 模擬上一場因連續失敗而暫停
        await c.start()
        resumed = c.status()["history_uid"]
        await c.stop()
        await c.start()
        fresh = c.status()["history_uid"]
        await c.stop()
        return first, resumed, fresh

    first, resumed, fresh = asyncio.run(run())
    assert resumed == first
    assert fresh != first
