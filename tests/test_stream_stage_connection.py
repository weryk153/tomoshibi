"""舞台頁連線不碰私人對話；直播中私人連線不能觸發回合。"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber import active_history_store
from src.open_llm_vtuber.chat_group import ChatGroupManager
from src.open_llm_vtuber.websocket_handler import WebSocketHandler


class FakeSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, payload):
        self.sent.append(json.loads(payload))


class FakeStream:
    def __init__(self, live=False, stage_uid=None):
        self.live = live
        self.stage_uid = stage_uid
        self.attached = []

    def attach_stage(self, uid):
        old = self.stage_uid if self.stage_uid not in (None, uid) else None
        self.stage_uid = uid
        self.attached.append(uid)
        return old

    def detach_stage(self, uid):
        if uid == self.stage_uid:
            self.stage_uid = None


def context():
    return SimpleNamespace(
        history_uid="",
        character_config=SimpleNamespace(conf_uid="frieren", conf_name="frieren"),
        live2d_model=SimpleNamespace(model_info={}),
        agent_engine=SimpleNamespace(set_memory_from_history=lambda **kw: None),
    )


def handler(stream):
    h = WebSocketHandler.__new__(WebSocketHandler)
    h.client_contexts = {}
    h.client_connections = {}
    h.client_last_active = {}
    h.current_conversation_tasks = {}
    h.received_data_buffers = {}
    h.chat_group_manager = ChatGroupManager()
    h.stream = stream
    return h


def connect(h, uid, stage):
    socket, ctx = FakeSocket(), context()
    h.client_connections[uid] = socket
    h.client_contexts[uid] = ctx
    h.chat_group_manager.client_group_map[uid] = ""
    asyncio.run(h._send_initial_messages(socket, uid, ctx, stage=stage))
    return socket, ctx


def types(socket):
    return [m["type"] for m in socket.sent]


@pytest.fixture(autouse=True)
def _tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_the_stage_does_not_touch_the_private_conversation():
    active_history_store.set_active_history_uid("frieren", "private-1")
    stream = FakeStream()
    h = handler(stream)
    socket, ctx = connect(h, "stage", stage=True)

    assert stream.stage_uid == "stage"
    assert ctx.history_uid == ""
    assert "history-data" not in types(socket)
    assert "new-history-created" not in types(socket)
    assert {"type": "control", "text": "start-mic"} not in socket.sent
    assert active_history_store.get_active_history_uid("frieren") == "private-1"

    asyncio.run(h._handle_create_history(socket, "stage", {}))
    asyncio.run(h._handle_fetch_history(socket, "stage", {"history_uid": "x"}))
    assert ctx.history_uid == ""
    assert active_history_store.get_active_history_uid("frieren") == "private-1"


def test_a_second_stage_tells_the_first_it_was_replaced():
    h = handler(FakeStream())
    first, _ = connect(h, "stage-1", stage=True)
    connect(h, "stage-2", stage=True)
    assert first.sent[-1] == {"type": "stage-replaced"}


def test_a_normal_client_learns_whether_a_stream_is_live():
    h = handler(FakeStream(live=True, stage_uid="stage"))
    socket, _ = connect(h, "me", stage=False)
    assert socket.sent[-1] == {"type": "stream-state", "live": True}


def test_private_triggers_are_refused_while_live():
    h = handler(FakeStream(live=True, stage_uid="stage"))
    me = FakeSocket()
    h.client_connections["me"] = me
    h.client_contexts["me"] = context()

    asyncio.run(
        h._handle_conversation_trigger(me, "me", {"type": "text-input", "text": "嗨"})
    )
    asyncio.run(h._handle_conversation_trigger(me, "me", {"type": "ai-speak-signal"}))
    asyncio.run(h._handle_config_switch(me, "me", {"file": "kurisu.yaml"}))

    assert h.current_conversation_tasks == {}
    assert [m.get("text_key") for m in me.sent if m["type"] == "error"] == [
        "privateChatPaused",
        "switchBlocked",
    ]


def test_the_stage_never_starts_its_own_turns():
    h = handler(FakeStream(live=True, stage_uid="stage"))
    stage = FakeSocket()
    h.client_connections["stage"] = stage
    h.client_contexts["stage"] = context()
    asyncio.run(
        h._handle_conversation_trigger(stage, "stage", {"type": "ai-speak-signal"})
    )
    assert h.current_conversation_tasks == {}
    assert stage.sent == []


def test_broadcast_skips_the_stage():
    h = handler(FakeStream(live=True, stage_uid="stage"))
    me, stage = FakeSocket(), FakeSocket()
    h.client_connections = {"me": me, "stage": stage}
    asyncio.run(h.broadcast_stream_state(False))
    assert me.sent == [{"type": "stream-state", "live": False}]
    assert stage.sent == []


def test_private_mic_audio_is_dropped_while_live():
    """直播中主視窗的麥克風不能累積語音、停播後一次送出去變成私人對話。"""
    import numpy as np

    h = handler(FakeStream(live=True, stage_uid="stage"))
    me = FakeSocket()
    h.client_connections["me"] = me
    h.client_contexts["me"] = context()
    h.received_data_buffers["me"] = np.array([0.1, 0.2], dtype=np.float32)

    asyncio.run(h._handle_audio_data(me, "me", {"audio": [0.3, 0.4]}))
    asyncio.run(h._handle_conversation_trigger(me, "me", {"type": "mic-audio-end"}))

    assert len(h.received_data_buffers["me"]) == 0
    assert h.current_conversation_tasks == {}
    # 前端講完話時切到「思考中」，要告訴它這一輪不會發生，回到閒置。
    assert {"type": "control", "text": "conversation-chain-end"} in me.sent
