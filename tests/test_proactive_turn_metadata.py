"""主動開口的 metadata 私人聊天和直播共用同一份組法。"""

from types import SimpleNamespace

from src.open_llm_vtuber.conversations.conversation_handler import (
    proactive_turn_metadata,
)
from src.open_llm_vtuber.proactive_context import proactive_context_uid


def test_metadata_matches_the_private_proactive_turn(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    context = SimpleNamespace(
        history_uid="h1",
        character_config=SimpleNamespace(conf_uid="frieren"),
        system_config=SimpleNamespace(tool_prompts={}),
    )
    metadata = proactive_turn_metadata(context, "client-1", ["screen"])
    assert metadata["proactive_speak"] is True
    assert metadata["skip_memory"] is True
    assert metadata["skip_history"] is True
    assert metadata["proactive_material"] == []
    assert metadata["proactive_instruction"] == ""
    assert metadata["proactive_image_sources"] == ["screen"]
    assert metadata["proactive_context_uid"] == proactive_context_uid("h1", "client-1")
    assert metadata["proactive_forbid_question"] is False
