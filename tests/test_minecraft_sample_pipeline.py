"""樣本要穿過實際對話生命週期和字幕管線，不能只測記錄函式。"""

import asyncio
import json
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig
from src.open_llm_vtuber.agent.output_types import Actions
from src.open_llm_vtuber.agent.transformers import display_processor, tts_filter
from src.open_llm_vtuber.conversations import single_conversation as conversation
from src.open_llm_vtuber.minecraft import goal_text, samples
from src.open_llm_vtuber.minecraft.feed import GameTurn, game_turn_metadata
from src.open_llm_vtuber.utils.sentence_divider import SentenceWithTags


@pytest.mark.parametrize("ending", ["ok", "failed", "interrupted"])
def test_game_conversation_records_raw_text_before_cleanup(
    tmp_path, monkeypatch, ending
):
    monkeypatch.chdir(tmp_path)
    goal_text._recent.clear()
    sent, displays = [], []
    raw = "minecraft_do: collect 10 oak logs\n先把木頭收齊。"

    async def sink(goal):
        sent.append(goal)

    monkeypatch.setattr(goal_text, "sink", sink)

    class Agent:
        @tts_filter(
            TTSPreprocessorConfig(
                remove_special_char=True,
                translator_config={
                    "translate_audio": False,
                    "translate_provider": "deeplx",
                },
            )
        )
        @display_processor()
        async def chat(self, batch):
            yield SentenceWithTags(text=raw, tags=[]), Actions()
            if ending == "failed":
                raise RuntimeError("fixture failure")
            if ending == "interrupted":
                raise asyncio.CancelledError

    async def nothing(*args, **kwargs):
        pass

    async def typed(text, *args, **kwargs):
        return text

    async def speak(output_item, **kwargs):
        displays.append(output_item)
        return output_item.display_text.text

    for name in (
        "send_conversation_start_signals",
        "finalize_conversation_turn",
        "send_character_mood",
    ):
        monkeypatch.setattr(conversation, name, nothing)
    monkeypatch.setattr(conversation, "process_user_input", typed)
    monkeypatch.setattr(conversation, "_speak", speak)
    monkeypatch.setattr(conversation, "cleanup_conversation", lambda *args: None)
    monkeypatch.setattr(conversation, "store_message", lambda **kwargs: None)
    monkeypatch.setattr(conversation.translation_audit, "flush_for", lambda *args: None)
    context = SimpleNamespace(
        agent_engine=Agent(),
        asr_engine=None,
        history_uid="history-1",
        system_config=None,
        character_config=SimpleNamespace(
            conf_uid="yura",
            human_name="me",
            character_name="yura",
            conf_name="yura",
            avatar="",
            reply_language="",
        ),
    )
    state = {"gameplay": {"health": 1}, "nearby": {"entityTypes": ["cow"]}}
    turn = GameTurn("idle", ("血量 1/20，附近有牛",), False, 12.0, state_raw=state)

    async def go():
        call = conversation.process_single_conversation(
            context,
            nothing,
            "client",
            "game turn",
            metadata=game_turn_metadata(turn.notes, turn=turn),
        )
        if ending == "interrupted":
            with pytest.raises(asyncio.CancelledError):
                await call
        else:
            await call
        await asyncio.sleep(0)
        assert samples.current_ref() is None

    asyncio.run(go())
    rows = [json.loads(line) for line in open(samples.path_for("yura"))]
    assert len(rows) == 1
    row = rows[0]
    assert row["raw_reply"] == raw
    assert row["goals"] == ["collect 10 oak logs"]
    assert row["state"] == state and row["history_uid"] == "history-1"
    assert row["notes"] == list(turn.notes) and row["result"] == ending
    assert sent == ["collect 10 oak logs"]
    assert displays[0].display_text.text == "先把木頭收齊。"
    assert "minecraft_do" not in displays[0].tts_text
