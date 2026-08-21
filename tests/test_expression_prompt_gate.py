"""live2d_expression_prompt is skipped for models that have nothing to express.

A model whose emotionMap holds a single entry (kurisu_fan ships with only
`neutral`) gains nothing from the expression prompt: one keyword cannot express
a contrast, so setting the sole expression is always a no-op.

Skipping it is not just a token saving. The prompt instructs "use them
regularly", the model complies, and the emitted `[neutral]` reaches
sentence_divider as ordinary content — splitting one reply into an extra
fragment that costs its own translate + TTS round trip. The logs caught it as
`SentenceWithTags(text='[neutral]\\n我这边反应有点延迟...')`.

The prompt must keep loading for models that do have a range (mao_pro ships
eight), so the gate has to discriminate rather than drop the feature.

Convention follows tests/test_persona_store.py: build a bare ServiceContext,
stub only what construct_system_prompt touches, and drive the coroutine with
asyncio.run (this repo has no pytest-asyncio).
"""

import asyncio
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber.service_context import ServiceContext

MAO_PRO_EMOTION_MAP = {
    "neutral": 0,
    "anger": 2,
    "disgust": 2,
    "fear": 1,
    "joy": 3,
    "smirk": 3,
    "sadness": 1,
    "surprise": 3,
}


class _Recorder:
    """Stands in for prompt_loader, recording which prompt files were asked for."""

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


def _build(emo_map: dict) -> ServiceContext:
    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(
        tool_prompts={"live2d_expression_prompt": "live2d_expression_prompt"},
        player_language="",
        player_prompt="",
    )
    context.live2d_model = SimpleNamespace(
        emo_map=emo_map,
        emo_str=" ".join(f"[{key}]," for key in emo_map),
        motion_str="",
    )
    # Long-term memory would pull in the core-memory store; this test is about
    # which prompt files load, so keep it off.
    context.character_config = SimpleNamespace(
        long_term_memory_enabled=False, conf_uid="test"
    )
    context.stage_director_prompt = ""
    return context


def test_single_expression_model_does_not_load_the_prompt(recorder):
    context = _build({"neutral": 0})

    result = asyncio.run(context.construct_system_prompt("你是紅莉栖。"))

    assert recorder.requested == []
    assert "<<live2d_expression_prompt>>" not in result


def test_empty_expression_map_does_not_load_the_prompt(recorder):
    context = _build({})

    result = asyncio.run(context.construct_system_prompt("你是紅莉栖。"))

    assert recorder.requested == []
    assert "<<live2d_expression_prompt>>" not in result


def test_model_with_a_real_range_still_loads_the_prompt(recorder):
    context = _build(MAO_PRO_EMOTION_MAP)

    result = asyncio.run(context.construct_system_prompt("你是貓娘。"))

    assert recorder.requested == ["live2d_expression_prompt"]
    assert "<<live2d_expression_prompt>>" in result


def test_two_expressions_are_enough_to_be_useful(recorder):
    """The gate asks "can this express a contrast", not "does it have many".

    Two keywords already let the character switch between states, so the
    boundary must sit at 2 — a stricter gate would silently disable expressions
    for small but working models.
    """
    context = _build({"neutral": 0, "joy": 3})

    asyncio.run(context.construct_system_prompt("你是誰。"))

    assert recorder.requested == ["live2d_expression_prompt"]
