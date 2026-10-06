"""用講的那一輪標成 TextSource.VOICE（ASR 還原只在這種輪跑）。

她讀到的字跟打字輪一樣：引擎那邊不因為是語音而多附東西。
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest

from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from src.open_llm_vtuber.conversations import (
    conversation_utils,
    group_conversation,
    single_conversation,
)

AUDIO = np.zeros(1600, dtype=np.float32)


# --- 輸入的來源 -------------------------------------------------------------------


def test_voice_is_its_own_text_source():
    assert TextSource.VOICE.value == "voice"
    assert TextSource.VOICE != TextSource.INPUT


def test_a_batch_is_typed_unless_told_it_was_spoken():
    typed = conversation_utils.create_batch_input("你好", None, "me")
    spoken = conversation_utils.create_batch_input(
        "你好", None, "me", source=TextSource.VOICE
    )
    assert [t.source for t in typed.texts] == [TextSource.INPUT]
    assert [t.source for t in spoken.texts] == [TextSource.VOICE]
    assert spoken.texts[0].content == "你好"


# --- 單人對話 ---------------------------------------------------------------------


class _Stop(Exception):
    pass


def _single_turn(monkeypatch, user_input, metadata=None):
    made = []

    async def transcribe(user_input, asr_engine, websocket_send, **_kwargs):
        return "歐嗨唷" if isinstance(user_input, np.ndarray) else user_input

    async def nothing(*_args, **_kwargs):
        return None

    def capture(**kwargs):
        made.append(kwargs)
        raise _Stop

    monkeypatch.setattr(single_conversation, "process_user_input", transcribe)
    monkeypatch.setattr(single_conversation, "send_conversation_start_signals", nothing)
    monkeypatch.setattr(single_conversation, "create_batch_input", capture)
    monkeypatch.setattr(single_conversation, "cleanup_conversation", lambda *a: None)

    context = SimpleNamespace(
        agent_engine=object(),
        asr_engine=None,
        history_uid="",
        character_config=SimpleNamespace(human_name="me"),
    )
    with pytest.raises(_Stop):
        asyncio.run(
            single_conversation.process_single_conversation(
                context, nothing, "client", user_input, metadata=metadata
            )
        )
    return made[0]


def test_a_spoken_turn_is_marked_as_voice(monkeypatch):
    made = _single_turn(monkeypatch, AUDIO)
    assert made["input_text"] == "歐嗨唷"
    assert made["source"] == TextSource.VOICE


def test_a_typed_turn_stays_input(monkeypatch):
    made = _single_turn(monkeypatch, "おはよう")
    assert made.get("source", TextSource.INPUT) == TextSource.INPUT


def test_a_proactive_turn_stays_input(monkeypatch):
    made = _single_turn(monkeypatch, "（主動開口）", metadata={"proactive_speak": True})
    assert made.get("source", TextSource.INPUT) == TextSource.INPUT


# --- 群組對話 ---------------------------------------------------------------------


def _group_chain(monkeypatch, user_input, turns=4):
    """跑一段群組對話：兩個成員輪流講，收到 turns 輪就停。"""
    made = []

    async def transcribe(user_input, asr_engine, websocket_send, **_kwargs):
        return "空尼七哇" if isinstance(user_input, np.ndarray) else user_input

    async def broadcast(*_args, **_kwargs):
        return None

    async def respond(**_kwargs):
        return "嗯。"

    def capture(**kwargs):
        made.append(kwargs)
        if len(made) >= turns:
            raise asyncio.CancelledError
        return SimpleNamespace()

    monkeypatch.setattr(group_conversation, "process_user_input", transcribe)
    monkeypatch.setattr(group_conversation, "create_batch_input", capture)
    monkeypatch.setattr(group_conversation, "process_member_response", respond)
    monkeypatch.setattr(group_conversation, "store_message", lambda **kw: None)

    def member(name):
        return SimpleNamespace(
            agent_engine=object(),
            asr_engine=None,
            history_uid=f"h-{name}",
            character_config=SimpleNamespace(
                human_name="me",
                character_name=name,
                conf_name=name,
                conf_uid=name,
                avatar="",
            ),
        )

    contexts = {"a": member("a"), "b": member("b")}
    connections = {uid: SimpleNamespace(send_text=broadcast) for uid in contexts}
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            group_conversation.process_group_conversation(
                client_contexts=contexts,
                client_connections=connections,
                broadcast_func=broadcast,
                group_members=["a", "b"],
                initiator_client_uid="a",
                user_input=user_input,
            )
        )
    return made


def test_a_spoken_group_turn_is_voice_only_where_the_human_line_is_heard(
    monkeypatch,
):
    made = _group_chain(monkeypatch, AUDIO)
    sources = [m.get("source", TextSource.INPUT) for m in made]
    # 每個成員第一次接話時，讀到的有使用者講的那句；之後輪到的只有彼此的回話。
    assert sources == [
        TextSource.VOICE,
        TextSource.VOICE,
        TextSource.INPUT,
        TextSource.INPUT,
    ]
    assert "空尼七哇" in made[0]["input_text"]
    assert "空尼七哇" not in made[2]["input_text"]


def test_a_typed_group_turn_stays_input(monkeypatch):
    made = _group_chain(monkeypatch, "こんにちは")
    assert {m.get("source", TextSource.INPUT) for m in made} == {TextSource.INPUT}


# --- 引擎那一輪 ---------------------------------------------------------------------

NOW = datetime(2026, 10, 6, 21, 30)


def _agent(tmp_path):
    pytest.importorskip("ai_character_engine")
    from tests.test_engine_agent import EngineLLM, agent, companion

    llm = EngineLLM()
    return agent(companion(tmp_path, llm), now=lambda: NOW), llm


def _batch(text, source, **metadata):
    return BatchInput(
        texts=[TextData(source=source, content=text)], metadata=metadata or None
    )


@pytest.mark.parametrize("text", ["你好", "要不要一起去？"])
def test_a_spoken_turn_reads_the_same_as_a_typed_one(tmp_path, text):
    current, _ = _agent(tmp_path)
    typed = current._turn(_batch(text, TextSource.INPUT), ())
    spoken = current._turn(_batch(text, TextSource.VOICE), ())
    assert spoken == typed
    assert spoken[0] == text


def test_letta_still_hears_spoken_words():
    letta = pytest.importorskip("src.open_llm_vtuber.agent.agents.letta_agent")
    agent = letta.LettaAgent.__new__(letta.LettaAgent)
    prompt = agent._to_text_prompt(_batch("歐嗨唷", TextSource.VOICE))
    assert prompt == "歐嗨唷"
