"""split_memory_blocks：把主機寫進系統提示的長期記憶再拿出來。

不需要引擎；character_engine_agent 怎麼用它在 test_engine_memory_notes.py。
"""

import pytest

from src.open_llm_vtuber.conversation_quality import CORE_CONVERSATION_PROMPT
from src.open_llm_vtuber.service_context import (
    build_memory_blocks,
    split_memory_blocks,
)

PERSONA = "你是紅莉栖。\n\n## 表情\n用 [joy] 這類標籤。"
TAIL = (
    f"\n\n{CORE_CONVERSATION_PROMPT}\n\n## Output language\nAlways write in 繁體中文."
)


def composed(self_memory="", core_memory=""):
    return PERSONA + build_memory_blocks(self_memory, core_memory) + TAIL


def test_the_memory_is_taken_out_and_the_rest_is_left_as_it_was():
    system = composed("紅莉栖：喜歡胡椒博士。", "對方：叫晨星。\n對方：養了一隻貓。")

    rest, about_her, about_the_user = split_memory_blocks(system)

    assert rest == PERSONA + TAIL
    assert about_her == "紅莉栖：喜歡胡椒博士。"
    assert about_the_user == "對方：叫晨星。\n對方：養了一隻貓。"


@pytest.mark.parametrize(
    "self_memory, core_memory",
    [("", ""), ("紅莉栖：喜歡胡椒博士。", ""), ("", "對方：叫晨星。")],
)
def test_either_memory_may_be_missing(self_memory, core_memory):
    rest, about_her, about_the_user = split_memory_blocks(
        composed(self_memory, core_memory)
    )

    assert rest == PERSONA + TAIL
    assert (about_her, about_the_user) == (self_memory, core_memory)


def test_a_prompt_composed_some_other_way_is_left_alone():
    """認不出結尾在哪裡的時候不要猜：切錯會把人設的一部分當成記憶拿走。"""
    system = PERSONA + build_memory_blocks("", "對方：叫晨星。") + "\n\n別的東西"

    assert split_memory_blocks(system) == (system, "", "")
