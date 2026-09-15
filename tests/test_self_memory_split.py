"""整理 LLM 的輸出分成兩段，缺一段就整輪作廢；self 段寫入前逐行過濾。

猜錯的後果是把對話記憶整份寫進 self_memory.md——那是唯一不能犯的錯，所以缺
標記時不猜。過濾擋得住代名詞（對方／你），擋不住名字；後者靠提示詞與設定頁。
"""

from src.open_llm_vtuber.memory_core import (
    SECTION_CONVERSATION,
    filter_self_lines,
    self_section_label,
    split_consolidation_output,
)

NAME = "紅莉栖"


def test_self_label_uses_the_character_name():
    assert self_section_label(NAME) == "【紅莉栖自己】"


def test_self_label_falls_back_without_a_name():
    assert self_section_label("") == "【角色自己】"
    assert self_section_label("   ") == "【角色自己】"


def test_splits_both_sections():
    text = (
        f"{SECTION_CONVERSATION}\n對方叫小明。\n對方喜歡貓。\n"
        f"{self_section_label(NAME)}\n紅莉栖最近迷上手沖咖啡。\n"
    )
    conv, self_ = split_consolidation_output(text, NAME)
    assert conv == "對方叫小明。\n對方喜歡貓。"
    assert self_ == "紅莉栖最近迷上手沖咖啡。"


def test_sections_may_come_in_either_order():
    text = (
        f"{self_section_label(NAME)}\n紅莉栖喜歡咖啡。\n"
        f"{SECTION_CONVERSATION}\n對方叫小明。\n"
    )
    conv, self_ = split_consolidation_output(text, NAME)
    assert conv == "對方叫小明。"
    assert self_ == "紅莉栖喜歡咖啡。"


def test_empty_section_is_empty_string_not_none():
    text = f"{SECTION_CONVERSATION}\n對方叫小明。\n{self_section_label(NAME)}\n"
    conv, self_ = split_consolidation_output(text, NAME)
    assert conv == "對方叫小明。"
    assert self_ == ""


def test_missing_self_marker_returns_none():
    assert (
        split_consolidation_output(f"{SECTION_CONVERSATION}\n對方叫小明。", NAME)
        is None
    )


def test_missing_conversation_marker_returns_none():
    assert (
        split_consolidation_output(f"{self_section_label(NAME)}\n她喜歡咖啡。", NAME)
        is None
    )


def test_no_markers_at_all_returns_none():
    assert split_consolidation_output("對方叫小明。\n她喜歡咖啡。", NAME) is None


def test_tolerates_backticks_and_whitespace_around_markers():
    text = (
        f"```\n  {SECTION_CONVERSATION}  \n對方叫小明。\n\n"
        f"  {self_section_label(NAME)}\n紅莉栖喜歡咖啡。\n```"
    )
    conv, self_ = split_consolidation_output(text, NAME)
    assert conv == "對方叫小明。"
    assert self_ == "紅莉栖喜歡咖啡。"


def test_filter_drops_lines_mentioning_the_other_party():
    text = "紅莉栖喜歡咖啡。\n紅莉栖和對方去過秋葉原。\n紅莉栖答應你下次帶書來。\n紅莉栖討厭夏天。"
    assert filter_self_lines(text) == "紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。"


def test_filter_keeps_everything_when_clean():
    text = "紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。"
    assert filter_self_lines(text) == text


def test_filter_on_empty_is_empty():
    assert filter_self_lines("") == ""
    assert filter_self_lines("\n\n") == ""
