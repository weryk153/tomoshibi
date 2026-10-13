"""Minecraft 這類後端自己觸發的主動開口：帶備註、不受「等你」模式擋。"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.conversations import conversation_handler as ch


def test_extra_metadata_is_merged_and_bypasses_wait_mode(monkeypatch):
    calls = []

    async def fake_process(**kwargs):
        calls.append(kwargs)
        return "嗯"

    monkeypatch.setattr(ch, "process_single_conversation", fake_process)
    monkeypatch.setattr(ch, "_speaks_up_now", lambda *_: False)
    monkeypatch.setattr(
        ch, "proactive_turn_metadata", lambda *a, **k: {"proactive_speak": True}
    )
    sent = []

    class Socket:
        async def send_text(self, payload):
            sent.append(payload)

    context = SimpleNamespace(
        history_uid="h1", character_config=SimpleNamespace(conf_uid="c")
    )
    tasks = {}
    group_manager = SimpleNamespace(get_client_group=lambda uid: None)

    async def go():
        await ch.handle_conversation_trigger(
            msg_type="ai-speak-signal",
            data={},
            client_uid="u1",
            context=context,
            websocket=Socket(),
            client_contexts={"u1": context},
            client_connections={},
            chat_group_manager=group_manager,
            received_data_buffers={},
            current_conversation_tasks=tasks,
            broadcast_to_group=None,
            extra_metadata={"notes": ["天黑了"]},
        )
        await tasks["u1"]

    asyncio.run(go())
    assert calls[0]["metadata"] == {"proactive_speak": True, "notes": ["天黑了"]}
    assert calls[0]["user_input"] == ch.PROACTIVE_TEXT


def test_without_extra_metadata_wait_mode_still_blocks(monkeypatch):
    monkeypatch.setattr(ch, "_speaks_up_now", lambda *_: False)
    tasks = {}

    async def go():
        await ch.handle_conversation_trigger(
            msg_type="ai-speak-signal",
            data={},
            client_uid="u1",
            context=SimpleNamespace(history_uid="h1"),
            websocket=None,
            client_contexts={},
            client_connections={},
            chat_group_manager=None,
            received_data_buffers={},
            current_conversation_tasks=tasks,
            broadcast_to_group=None,
        )

    asyncio.run(go())
    assert tasks == {}
