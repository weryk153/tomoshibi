"""每個角色共用的說話規則放在系統提示最前面，人設只留角色本身。

2026-10-02 對照（芙莉蓮、紅莉栖 × 6 情境 × 3 次，qwen3.5-9b）：同一份規則接在系統
提示後段時，紅莉栖被問 AI 與聲音時偏離身分表、芙莉蓮「嗯」開頭 0→4/18；放在最前面
才回到原本的水準。位置本身就是規則的一部分，所以這裡把它釘住。
"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.conversation_quality import (
    ACTION_RULES,
    CORE_CONVERSATION_PROMPT,
    SPEECH_RULES,
)
from src.open_llm_vtuber.service_context import ServiceContext


def _context(actions_enabled: bool = False, tool_prompts=None) -> ServiceContext:
    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(
        tool_prompts=tool_prompts or {}, player_language="", player_prompt=""
    )
    context.live2d_model = SimpleNamespace(emo_map={}, emo_str="", motion_str="")
    context.character_config = SimpleNamespace(
        long_term_memory_enabled=False,
        conf_uid="test",
        reply_language="",
        actions_enabled=actions_enabled,
    )
    context.stage_director_prompt = ""
    return context


def test_the_speech_rules_open_the_system_prompt():
    prompt = asyncio.run(_context().construct_system_prompt("PERSONA"))

    assert prompt.startswith(SPEECH_RULES)
    assert prompt.index(SPEECH_RULES) < prompt.index("PERSONA")
    assert prompt.index("PERSONA") < prompt.index(CORE_CONVERSATION_PROMPT)
    assert prompt.count(SPEECH_RULES) == 1


def test_the_rules_say_what_the_persona_used_to_repeat():
    for rule in ("一到三句", "「嗯」", "好久不見", "「是。」", "「作品」"):
        assert rule in SPEECH_RULES


def test_the_rules_say_what_the_persona_used_to_repeat_without_actions():
    assert "星號" not in SPEECH_RULES
    assert "星號" in ACTION_RULES


def _with_think_tag(monkeypatch, actions_enabled):
    from src.open_llm_vtuber import service_context

    monkeypatch.setattr(
        service_context.prompt_loader,
        "load_util",
        lambda name: "THINK-TAG-PROMPT" if name == "think_tag_prompt_zh" else "",
    )
    context = _context(
        actions_enabled, tool_prompts={"think_tag_prompt": "think_tag_prompt_zh"}
    )
    return asyncio.run(context.construct_system_prompt("PERSONA"))


def test_a_character_that_may_write_actions_gets_the_action_format(monkeypatch):
    """開關開著：共用規則後面接動作格式，think_tag 提示照樣附上（實測格式最穩）。"""
    prompt = _with_think_tag(monkeypatch, actions_enabled=True)

    assert prompt.startswith(SPEECH_RULES)
    assert prompt.index(ACTION_RULES) < prompt.index("PERSONA")
    assert "THINK-TAG-PROMPT" in prompt


def test_a_character_that_does_not_write_actions_hears_nothing_about_them(
    monkeypatch,
):
    """開關關著：提示裡完全不提動作。只要一提（連教格式的範例都算），不寫動作的
    角色就會開始寫——紅莉栖 0/18 → 3/18。"""
    prompt = _with_think_tag(monkeypatch, actions_enabled=False)

    assert ACTION_RULES not in prompt
    assert "THINK-TAG-PROMPT" not in prompt
