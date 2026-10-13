"""跟 MindServer 的 socket.io 連線：事件怎麼進來、送話怎麼出去、等回話怎麼等。"""

import asyncio

import pytest

from src.open_llm_vtuber.minecraft.mindserver import MindServerClient


class FakeSio:
    """假的 socketio.AsyncClient：記下 emit，讓測試自己觸發 handler。"""

    def __init__(self, fail_connect=False):
        self.handlers = {}
        self.emits = []
        self.connected = False
        self.fail_connect = fail_connect

    def on(self, event, handler=None):
        if handler is None:

            def wrap(fn):
                self.handlers[event] = fn
                return fn

            return wrap
        self.handlers[event] = handler
        return handler

    async def connect(self, url, **kwargs):
        if self.fail_connect:
            raise OSError("refused")
        self.connected = True
        self.url = url
        handler = self.handlers.get("connect")
        if handler:
            await handler()

    async def emit(self, event, data=None):
        self.emits.append((event, data))

    async def disconnect(self):
        self.connected = False

    async def shutdown(self):
        self.shut_down = True
        self.connected = False

    async def fire(self, event, *args):
        result = self.handlers[event](*args)
        if asyncio.iscoroutine(result):
            await result


def make(**kw):
    sio = FakeSio(**kw)
    client = MindServerClient(
        "http://127.0.0.1:8080", "frieren", make_client=lambda: sio
    )
    return sio, client


def test_connect_subscribes_to_agent_state():
    sio, client = make()
    asyncio.run(client.connect())
    assert sio.url == "http://127.0.0.1:8080"
    assert ("listen-to-agents", None) in sio.emits
    assert client.connected


def test_connect_failure_is_a_connection_error():
    sio, client = make(fail_connect=True)
    with pytest.raises(ConnectionError):
        asyncio.run(client.connect())


def test_state_and_status_only_for_her_bot():
    sio, client = make()
    seen = []
    client.on_state = seen.append

    async def go():
        await client.connect()
        await sio.fire(
            "state-update", {"frieren": {"gameplay": {"health": 7}}, "andy": {}}
        )
        await sio.fire(
            "agents-status",
            [{"name": "andy", "in_game": True}, {"name": "frieren", "in_game": False}],
        )
        assert not client.in_game
        await sio.fire("agents-status", [{"name": "frieren", "in_game": True}])
        assert client.in_game

    asyncio.run(go())
    assert seen == [{"gameplay": {"health": 7}}]


def test_output_goes_to_callback_unless_someone_is_asking():
    sio, client = make()
    outputs = []
    client.on_output = outputs.append

    async def go():
        await client.connect()
        await sio.fire("bot-output", "frieren", "Hello!")
        await sio.fire("bot-output", "andy", "ignored")
        asking = asyncio.create_task(
            client.ask("芙莉蓮", "collect 10 oak logs", timeout=5)
        )
        await asyncio.sleep(0)
        assert sio.emits[-1] == (
            "send-message",
            ("frieren", {"from": "芙莉蓮", "message": "collect 10 oak logs"}),
        )
        await sio.fire("bot-output", "frieren", "On it! !collectBlocks")
        assert await asking == "On it! !collectBlocks"
        await sio.fire("bot-output", "frieren", "Done.")

    asyncio.run(go())
    assert outputs == ["Hello!", "Done."]


def test_ask_times_out_to_none():
    sio, client = make()

    async def go():
        await client.connect()
        return await client.ask("芙莉蓮", "x", timeout=0.01)

    assert asyncio.run(go()) is None


def test_disconnect_callback_and_resubscribe_on_reconnect():
    sio, client = make()
    dropped = []
    client.on_disconnect = lambda: dropped.append(1)

    async def go():
        await client.connect()
        await sio.fire("disconnect")
        assert not client.in_game
        await sio.fire("connect")

    asyncio.run(go())
    assert dropped == [1]
    assert [e for e, _ in sio.emits].count("listen-to-agents") == 2


def test_close_calls_shutdown_and_silences_callbacks():
    sio, client = make()
    seen = []
    client.on_state = seen.append

    async def go():
        await client.connect()
        await client.close()
        await sio.fire("state-update", {"frieren": {}})

    asyncio.run(go())
    assert sio.shut_down
    assert seen == []


def test_raising_callback_does_not_break_disconnect_handler():
    sio, client = make()

    def boom():
        raise RuntimeError("x")

    client.on_disconnect = boom

    async def go():
        await client.connect()
        await sio.fire("disconnect")

    asyncio.run(go())
    assert not client.in_game


def test_concurrent_asks_each_get_their_own_reply():
    sio, client = make()

    async def go():
        a = asyncio.create_task(client.ask("她", "one", timeout=5))
        b = asyncio.create_task(client.ask("她", "two", timeout=5))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await sio.fire("bot-output", "frieren", "reply-1")
        assert await a == "reply-1"
        await asyncio.sleep(0)
        await sio.fire("bot-output", "frieren", "reply-2")
        assert await b == "reply-2"

    asyncio.run(go())
