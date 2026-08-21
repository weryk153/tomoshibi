import asyncio
import json
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber import persona_store
from src.open_llm_vtuber.service_context import ServiceContext


@pytest.fixture()
def isolated_store(tmp_path, monkeypatch):
    persona_dir = tmp_path / "personas"
    monkeypatch.setattr(persona_store, "PERSONAS_DIR", str(persona_dir))
    monkeypatch.setattr(
        persona_store,
        "STORE_PATH",
        str(persona_dir / "personas.json"),
    )
    return persona_dir


def test_persona_crud_and_active_selection_are_character_independent(isolated_store):
    calm = persona_store.create_persona("沉穩理性", "說話沉穩、有主見。", "calm")
    playful = persona_store.create_persona("活潑", "自然活潑，偶爾開玩笑。", "playful")

    assert [item["id"] for item in persona_store.list_personas()] == [
        "calm",
        "playful",
    ]

    persona_store.set_active_persona("character_a", calm["id"])
    persona_store.set_active_persona("character_b", playful["id"])
    assert persona_store.get_active_persona_id("character_a") == "calm"
    assert persona_store.get_active_persona_id("character_b") == "playful"
    assert persona_store.is_persona_active("calm") is True

    updated = persona_store.update_persona("calm", "冷靜", "冷靜但不冷淡。")
    assert updated["prompt"] == "冷靜但不冷淡。"
    assert persona_store.resolve_active_persona("character_a") == updated

    persona_store.set_active_persona("character_a", None)
    assert persona_store.get_active_persona_id("character_a") is None
    assert persona_store.delete_persona("calm") is True
    assert persona_store.get_persona("calm") is None


def test_persona_validation(isolated_store):
    with pytest.raises(ValueError, match="name"):
        persona_store.create_persona("", "prompt")
    with pytest.raises(ValueError, match="prompt"):
        persona_store.create_persona("name", "")
    with pytest.raises(ValueError, match="ID"):
        persona_store.create_persona("name", "prompt", "../escape")


def test_hot_apply_changes_only_prompt_and_can_restore_default(
    isolated_store,
):
    persona_store.create_persona("直接", "直接、有主見。", "direct")

    class FakeAgent:
        def __init__(self):
            self.system = None

        def set_system(self, system):
            self.system = system

    class FakeWebSocket:
        def __init__(self):
            self.messages = []

        async def send_text(self, value):
            self.messages.append(json.loads(value))

    context = ServiceContext()
    context.character_config = SimpleNamespace(
        conf_uid="same_character",
        persona_prompt="角色原本人設",
    )
    context.config = SimpleNamespace(character_config=context.character_config)
    context.character_persona_prompt = "角色原本人設"
    context.agent_engine = FakeAgent()

    async def fake_construct(prompt):
        return f"SYSTEM::{prompt}"

    context.construct_system_prompt = fake_construct
    websocket = FakeWebSocket()

    asyncio.run(context.apply_persona(websocket, "direct"))
    assert context.character_config.conf_uid == "same_character"
    assert context.character_config.persona_prompt == "直接、有主見。"
    assert context.agent_engine.system == "SYSTEM::直接、有主見。"
    assert persona_store.get_active_persona_id("same_character") == "direct"
    assert websocket.messages[-1]["type"] == "persona-switched"

    asyncio.run(context.apply_persona(websocket, None))
    assert context.character_config.persona_prompt == "角色原本人設"
    assert context.agent_engine.system == "SYSTEM::角色原本人設"
    assert persona_store.get_active_persona_id("same_character") is None
