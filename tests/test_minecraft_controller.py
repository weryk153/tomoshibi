"""Minecraft 模式的開始、停止、狀態；直播中讓位給直播流程。"""

import asyncio

import pytest

from src.open_llm_vtuber.config_manager.minecraft import MinecraftConfig
from src.open_llm_vtuber.minecraft.controller import MinecraftController, MinecraftError


class FakeClient:
    instances = []

    def __init__(self, url, bot_name, *, fail=False):
        self.url, self.bot_name, self.fail = url, bot_name, fail
        self.connected = False
        self.in_game = True
        self.closed = False
        self.on_state = self.on_output = self.on_disconnect = None
        FakeClient.instances.append(self)

    async def connect(self):
        if self.fail:
            raise ConnectionError("refused")
        self.connected = True

    async def close(self):
        self.closed = True

    async def ask(self, from_name, message, timeout):
        return "ok"


class FakeHost:
    def __init__(self):
        self.installed = None
        self.turns = []

    def speaker_name(self):
        return "芙莉蓮"

    def install_tool(self, handler):
        self.installed = handler

    def uninstall_tool(self):
        self.installed = None

    async def run_private_turn(self, turn):
        self.turns.append(turn)
        return "ok"


class FakeStream:
    def __init__(self):
        self.live = False
        self.attached = []

    def attach_extra(self, source):
        self.attached.append(source)

    def detach_extra(self):
        self.attached.append(None)


def controller(host=None, stream=None, bot_name="frieren", fail=False):
    settings = MinecraftConfig(
        bot_name=bot_name, idle_seconds=3, idle_cooldown_seconds=0
    )
    return MinecraftController(
        host or FakeHost(),
        stream=stream,
        make_client=lambda url, name: FakeClient(url, name, fail=fail),
        read_settings=lambda: settings,
        write_settings=lambda changes: settings,
        session_options={"clock": lambda: 0.0, "sleep": lambda s: asyncio.sleep(0)},
    )


async def _until(predicate):
    for _ in range(500):
        if predicate():
            return
        await asyncio.sleep(0)
    raise AssertionError("condition never met")


def test_start_connects_installs_tool_attaches_to_stream_and_stop_cleans_up():
    host, stream = FakeHost(), FakeStream()
    c = controller(host, stream)

    async def go():
        status = await c.start()
        assert status["live"] and status["connected"]
        assert host.installed is not None
        assert len(stream.attached) == 1 and stream.attached[0] is not None
        with pytest.raises(MinecraftError) as error:
            await c.start()
        assert error.value.reason == "already_live"
        stopped = await c.stop()
        assert not stopped["live"] and stopped["stopped_reason"] == "stopped"
        assert host.installed is None
        assert stream.attached[-1] is None
        assert FakeClient.instances[-1].closed

    asyncio.run(go())


def test_start_errors():
    with pytest.raises(MinecraftError) as e:
        asyncio.run(controller(bot_name="").start())
    assert e.value.reason == "no_bot_name"
    with pytest.raises(MinecraftError) as e:
        asyncio.run(controller(fail=True).start())
    assert e.value.reason == "not_running"


def test_state_from_client_reaches_her_and_status_shows_it():
    host = FakeHost()
    c = controller(host)

    async def go():
        await c.start()
        client = FakeClient.instances[-1]
        client.on_state(
            {"gameplay": {"health": 5}, "action": {"current": "dig", "isIdle": False}}
        )
        client.on_state(
            {"gameplay": {"health": 0}, "action": {"current": "dig", "isIdle": False}}
        )
        await _until(lambda: host.turns)
        assert host.turns[0].urgent
        assert c.status()["health"] == 0 and c.status()["action"] == "dig"
        await c.stop()

    asyncio.run(go())


def test_apply_settings_swaps_feed_rules_while_live():
    c = controller()

    async def go():
        await c.start()
        c.apply_settings(
            MinecraftConfig(
                bot_name="frieren", idle_seconds=99, event_cooldown_seconds=7
            )
        )
        assert c._feed.rules.idle_seconds == 99 and c._feed.rules.event_cooldown == 7
        await c.stop()

    asyncio.run(go())


def test_stop_when_not_live_is_harmless():
    assert asyncio.run(controller().stop())["live"] is False


def test_idle_turns_only_while_the_bot_is_in_game():
    host = FakeHost()
    now = {"t": 0.0}
    settings = MinecraftConfig(
        bot_name="frieren", idle_seconds=3, idle_cooldown_seconds=1000
    )
    c = MinecraftController(
        host,
        make_client=lambda url, name: FakeClient(url, name),
        read_settings=lambda: settings,
        write_settings=lambda changes: settings,
        session_options={
            "clock": lambda: now["t"],
            "sleep": lambda s: asyncio.sleep(0),
        },
    )
    idle = {"gameplay": {"health": 20}, "action": {"current": "Idle", "isIdle": True}}

    async def go():
        await c.start()
        client = FakeClient.instances[-1]
        client.in_game = False
        client.on_state(idle)
        now["t"] = 100.0
        for _ in range(50):
            await asyncio.sleep(0)
        assert host.turns == []
        client.in_game = True
        await _until(lambda: host.turns)
        assert host.turns[0].kind == "idle"
        # 冷卻很長：只該有一輪，也避免空轉的迴圈餓死事件圈
        await c.stop()

    asyncio.run(go())


def test_concurrent_starts_connect_only_one_client():
    c = controller()
    before = len(FakeClient.instances)

    async def go():
        results = await asyncio.gather(c.start(), c.start(), return_exceptions=True)
        errors = [r for r in results if isinstance(r, MinecraftError)]
        assert len(errors) == 1 and errors[0].reason == "already_live"
        assert len(FakeClient.instances) == before + 1
        await c.stop()

    asyncio.run(go())


def test_a_failure_after_connect_closes_the_client():
    class BadHost(FakeHost):
        def install_tool(self, handler):
            raise RuntimeError("boom")

    c = controller(BadHost())

    async def go():
        with pytest.raises(RuntimeError):
            await c.start()
        assert FakeClient.instances[-1].closed
        assert not c.live

    asyncio.run(go())


def test_the_stream_path_gets_no_idle_turn_while_the_bot_is_out_of_game():
    stream = FakeStream()
    c = controller(None, stream)
    idle = {"gameplay": {"health": 20}, "action": {"current": "Idle", "isIdle": True}}

    async def go():
        await c.start()
        client = FakeClient.instances[-1]
        feed = stream.attached[0]  # 直播流程拿到的就是這個 feed
        client.on_state(idle)
        client.in_game = False
        assert feed.pick(1000.0) is None
        client.in_game = True
        turn = feed.pick(1000.0)
        assert turn is not None and turn.kind == "idle"
        await c.stop()

    asyncio.run(go())


def test_text_goal_waits_until_the_body_is_idle():
    """她講話時身體不停：身體在忙，目標先排著，閒下來那一秒才送。"""
    from src.open_llm_vtuber.minecraft import goal_text

    class SendingClient(FakeClient):
        def __init__(self, url, bot_name):
            super().__init__(url, bot_name)
            self.sent = []

        async def send(self, from_name, message):
            self.sent.append(message)

    host = FakeHost()
    settings = MinecraftConfig(
        bot_name="frieren", idle_seconds=3, idle_cooldown_seconds=0
    )
    c = MinecraftController(
        host,
        make_client=lambda url, name: SendingClient(url, name),
        read_settings=lambda: settings,
        write_settings=lambda changes: settings,
        session_options={"clock": lambda: 0.0, "sleep": lambda s: asyncio.sleep(0)},
    )

    async def go():
        await c.start()
        client = c._client
        client.on_state(
            {
                "gameplay": {"health": 20},
                "action": {"current": "collectBlocks", "isIdle": False},
            }
        )
        await goal_text.sink("craft a crafting table")
        assert client.sent == []  # 身體在忙，先排著
        client.on_state(
            {"gameplay": {"health": 20}, "action": {"current": "Idle", "isIdle": True}}
        )
        await asyncio.sleep(0)
        assert client.sent == ['!craftRecipe("oak_planks", 1)']  # 編成指令，一次一步
        c._sent_at = float("-inf")  # 假裝幾秒過去
        client.on_state(
            {"gameplay": {"health": 20}, "action": {"current": "Idle", "isIdle": True}}
        )
        await asyncio.sleep(0)
        assert client.sent[-1] == '!craftRecipe("crafting_table", 1)'
        await c.stop()

    asyncio.run(go())


def test_native_tool_queues_and_late_body_report_stays_with_earlier_round(
    tmp_path, monkeypatch
):
    import json
    from src.open_llm_vtuber.minecraft import samples

    monkeypatch.chdir(tmp_path)
    host = FakeHost()
    c = controller(host)

    async def go():
        await c.start()
        client = c._client
        sent = []

        async def send(name, message):
            sent.append(message)

        client.send = send
        idle = {"gameplay": {"health": 20}, "action": {"isIdle": True}}
        client.on_state(idle)
        token = samples.start("yura", "idle", ["A"], idle)
        a = samples.current_ref()
        await host.installed(goal="collect 10 oak logs")
        samples.finish("ok", token)
        assert sent == ['!collectBlocks("oak_log", 10)']
        client.on_state({"gameplay": {"health": 20}, "action": {"isIdle": False}})
        token = samples.start("yura", "event", ["B"], idle)
        b = samples.current_ref()
        await host.installed(goal="craft a crafting table")
        samples.finish("ok", token)
        assert len(sent) == 1  # 原生工具不能搶掉 A
        client.on_output("Collected 10 oak logs")
        c._sent_at = float("-inf")
        client.on_state(idle)
        await asyncio.sleep(0)
        client.on_output("Crafted oak planks")
        await c.stop()
        return a, b

    a, b = asyncio.run(go())
    rows = [json.loads(line) for line in open(a.path)]
    reports = [row for row in rows if row.get("event") == "body_output"]
    assert [row["outcome_of"] for row in reports] == [a.id, b.id]
    assert all(
        row["command_id"] and row["association"] == "active_command_at_receipt"
        for row in reports
    )
    cancelled = [row for row in rows if row.get("event") == "command_cancelled"]
    assert cancelled[0]["reason"] == "mode_stopped"


def test_queue_needs_fresh_state_and_disconnect_discards_unsent_steps():
    host = FakeHost()
    c = controller(host)

    async def go():
        await c.start()
        client = c._client
        sent = []

        async def send(*args):
            sent.append(args)

        client.send = send
        await host.installed(goal="craft a crafting table")
        assert not sent  # 尚未收到任何狀態
        idle = {"gameplay": {"health": 20}, "action": {"isIdle": True}}
        client.on_state(idle)
        c._state_at -= 10
        await asyncio.sleep(0)
        assert not sent  # 舊狀態不能當成仍閒著
        client.on_state(idle)
        await asyncio.sleep(0)
        assert len(sent) == 1
        client.on_disconnect()
        c._sent_at = float("-inf")
        client.on_state(idle)
        await asyncio.sleep(0)
        assert len(sent) == 1 and not c._queue
        await c.stop()

    asyncio.run(go())


def test_send_failure_is_recorded_and_remaining_recipe_steps_are_cancelled(
    tmp_path, monkeypatch
):
    import json
    from src.open_llm_vtuber.minecraft import samples

    monkeypatch.chdir(tmp_path)
    c = controller()

    async def go():
        await c.start()

        async def fail(*args):
            raise ConnectionError("socket gone")

        c._client.send = fail
        c._client.on_state({"gameplay": {}, "action": {"isIdle": True}})
        token = samples.start("yura", "idle", [], {})
        await c._host.installed(goal="craft a crafting table")
        samples.finish("ok", token)
        assert not c._queue
        assert "socket gone" in c.last_error
        await c.stop()

    asyncio.run(go())
    rows = [json.loads(line) for line in open(samples.path_for("yura"))]
    assert any(row.get("event") == "command_send_failed" for row in rows)
    assert any(row.get("reason") == "send_failed" for row in rows)


def test_stop_cancels_a_sending_task_before_it_can_leak_into_restart():
    host = FakeHost()
    c = controller(host)

    async def go():
        await c.start()
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def send(*args):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        c._client.send = send
        c._client.on_state({"gameplay": {}, "action": {"isIdle": True}})
        sending = asyncio.create_task(host.installed(goal="collect 10 oak logs"))
        await started.wait()
        await c.stop()
        await asyncio.gather(sending, return_exceptions=True)
        assert cancelled.is_set() and not c._pump_tasks
        await c.start()
        assert not c._queue and c._active is None
        await c.stop()

    asyncio.run(go())
