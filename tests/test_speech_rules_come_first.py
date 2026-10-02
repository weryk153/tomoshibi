"""每個角色共用的說話規則放在系統提示最前面，人設只留角色本身。

2026-10-02 對照（芙莉蓮、紅莉栖 × 6 情境 × 3 次，qwen3.5-9b）：同一份規則接在系統
提示後段時，紅莉栖被問 AI 與聲音時偏離身分表、芙莉蓮「嗯」開頭 0→4/18；放在最前面
才回到原本的水準。位置本身就是規則的一部分，所以這裡把它釘住。
"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.conversation_quality import (
    CORE_CONVERSATION_PROMPT,
    SPEECH_RULES,
)
from src.open_llm_vtuber.service_context import ServiceContext


def _context() -> ServiceContext:
    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(
        tool_prompts={}, player_language="", player_prompt=""
    )
    context.live2d_model = SimpleNamespace(emo_map={}, emo_str="", motion_str="")
    context.character_config = SimpleNamespace(
        long_term_memory_enabled=False, conf_uid="test", reply_language=""
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
    for rule in ("一到三句", "「嗯」", "好久不見", "星號", "「作品」"):
        assert rule in SPEECH_RULES
