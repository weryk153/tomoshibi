"""主動開口：引擎 agent 只要素材與規矩；送去的文字只是佔位，但不能是空的。"""

import inspect

from src.open_llm_vtuber.conversations import conversation_handler, single_conversation


def test_a_proactive_turn_still_reaches_the_engine():
    src = inspect.getsource(conversation_handler)
    assert 'PROACTIVE_TEXT = "（主動開口）"' in src
    assert "build_proactive_prompt" not in src
    assert '"proactive_material": material,' in src
    assert '"proactive_instruction": instruction,' in src


def test_the_host_keeps_only_what_only_the_host_knows():
    src = inspect.getsource(single_conversation.process_single_conversation)
    assert "breaks_what_the_host_knows(" in src
    for gone in (
        "own_checks",
        "should_suppress_proactive_text",
        "is_generic_assistant_boilerplate",
        "ResponseRepetitionGuard",
        "record_reply",
        "consolidate_core_memory",
        "build_recent_reply_guidance",
    ):
        assert gone not in src, gone
