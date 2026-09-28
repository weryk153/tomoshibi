"""character_engine_agent 的設定。

前景的設定（llm_provider、use_mcpp…）沿用 basic_memory_agent 那個區塊；
character_engine_agent 自己的區塊只放認知的節奏。
"""

import pytest
from pydantic import ValidationError

from src.open_llm_vtuber.config_manager.agent import (
    AgentSettings,
    CharacterEngineAgentConfig,
)
from src.open_llm_vtuber.config_manager.utils import read_yaml, validate_config


def test_the_engine_block_can_be_left_out_entirely():
    settings = AgentSettings(basic_memory_agent={"llm_provider": "lmstudio_llm"})

    assert settings.character_engine_agent is None


def test_defaults_match_what_was_measured_on_a_local_model():
    config = CharacterEngineAgentConfig()

    assert config.model_dump() == {
        "emotion_every": 1,
        "memory_every": 2,
        "summary_every": 0,
        "reflection_every": 6,
        "goal_every": 4,
        "timeout_seconds": 60.0,
        "max_rebase_turns": 3,
        "goal_max_age_days": 7,
        "foreground_patience_seconds": 120.0,
    }


def test_zero_turns_a_worker_off():
    assert CharacterEngineAgentConfig(goal_every=0).goal_every == 0


@pytest.mark.parametrize(
    "bad", [{"emotion_every": -1}, {"timeout_seconds": 0}, {"max_rebase_turns": -2}]
)
def test_values_that_make_no_sense_are_rejected_when_the_config_loads(bad):
    with pytest.raises(ValidationError):
        CharacterEngineAgentConfig(**bad)


@pytest.mark.parametrize(
    "template",
    ["config_templates/conf.default.yaml", "config_templates/conf.ZH.default.yaml"],
)
def test_both_templates_accept_the_engine_agent_as_a_choice(template):
    data = read_yaml(template)
    agent = data["character_config"]["agent_config"]
    assert "character_engine_agent" in agent["agent_settings"]

    agent["conversation_agent_choice"] = "character_engine_agent"

    config = validate_config(data)
    chosen = config.character_config.agent_config
    assert chosen.conversation_agent_choice == "character_engine_agent"
    assert chosen.agent_settings.character_engine_agent.reflection_every == 6


def test_settings_reach_the_engine_session_unchanged():
    pytest.importorskip("ai_character_engine")
    from src.open_llm_vtuber.character_engine.session import CognitionSettings

    dumped = CharacterEngineAgentConfig(goal_every=4).model_dump()

    assert CognitionSettings(**dumped).goal_every == 4
