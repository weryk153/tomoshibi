"""expression_source: background 時系統提示不教標籤；tags（預設）一字不差。

表情與動作改由背景模型逐句挑（expression_pick），主模型不必再學 [joy] 這套。
沒設背景模型、或引擎太舊（1.3.0 以前）時 background 不成立，提示照舊教標籤——不然她一個表情都沒有。
"""

import asyncio
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber.service_context import ServiceContext

try:
    from ai_character_engine.companion import AvatarChoices  # noqa: F401

    ENGINE_PICKS = True
except ImportError:  # 引擎 1.3.0 以前挑不了，background 照舊教標籤
    ENGINE_PICKS = False

TAG_PROMPTS = ("live2d_expression_prompt", "live2d_motion_prompt", "vrm_motion_prompt")


class _Recorder:
    def __init__(self):
        self.requested: list[str] = []

    def load_util(self, name: str) -> str:
        self.requested.append(name)
        return f"<<{name}>>"


@pytest.fixture
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr("src.open_llm_vtuber.service_context.prompt_loader", rec)
    return rec


def _character(source=None, *, background=True):
    engine = SimpleNamespace(
        background_base_url="http://127.0.0.1:1235/v1" if background else "",
        background_model="qwen/qwen3.5-9b" if background else "",
        background_api_key="",
    )
    character = SimpleNamespace(
        long_term_memory_enabled=False,
        conf_uid="test",
        agent_config=SimpleNamespace(
            agent_settings=SimpleNamespace(
                character_engine_agent=engine,
                conversation=SimpleNamespace(llm_provider="lmstudio_llm"),
            ),
            llm_configs=SimpleNamespace(
                lmstudio_llm=SimpleNamespace(extra_body={}, llm_api_key="")
            ),
        ),
    )
    if source is not None:
        character.expression_source = source
    return character


def _context(character) -> ServiceContext:
    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(
        tool_prompts={
            "live2d_expression_prompt": "live2d_expression_prompt",
            "live2d_motion_prompt": "live2d_motion_prompt",
            "vrm_motion_prompt": "vrm_motion_prompt",
            "speakable_prompt": "speakable_prompt",
        },
        player_language="",
        player_prompt="",
    )
    context.live2d_model = SimpleNamespace(
        emo_map={"neutral": 0, "joy": 3},
        emo_str="[neutral], [joy],",
        motion_str="[nod],",
        type="live2d",
    )
    context.character_config = character
    context.stage_director_prompt = ""
    return context


def _prompt(character):
    return asyncio.run(_context(character).construct_system_prompt("你是詠梨。"))


@pytest.mark.skipif(not ENGINE_PICKS, reason="ai-character-engine 1.3.0 or later")
def test_background_mode_teaches_no_tags(recorder):
    prompt = _prompt(_character("background"))

    assert recorder.requested == ["speakable_prompt"]
    for name in TAG_PROMPTS:
        assert f"<<{name}>>" not in prompt
    assert "<<speakable_prompt>>" in prompt


def test_tags_mode_is_exactly_what_it_always_was(recorder):
    before = _prompt(_character())
    tags = _prompt(_character("tags"))

    assert tags == before
    assert "<<live2d_expression_prompt>>" in tags
    assert "<<live2d_motion_prompt>>" in tags


def test_background_without_a_background_model_still_teaches_tags(recorder):
    assert _prompt(_character("background", background=False)) == _prompt(_character())
