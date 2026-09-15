"""整理 LLM 的輸出分成兩段，缺一段就整輪作廢；self 段寫入前逐行過濾。

猜錯的後果是把對話記憶整份寫進 self_memory.md——那是唯一不能犯的錯，所以缺
標記時不猜。過濾擋得住代名詞（對方／你），擋不住名字；後者靠提示詞與設定頁。
"""

from src.open_llm_vtuber.memory_core import (
    SELF_CAP_CHARS,
    SECTION_CONVERSATION,
    build_consolidation_prompt,
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


def test_self_section_with_only_placeholder_is_empty():
    text = (
        f"{SECTION_CONVERSATION}\n對方叫小明。\n"
        f"{self_section_label(NAME)}\n（目前還沒有任何關於自己的記憶）\n"
    )
    conv, self_ = split_consolidation_output(text, NAME)
    assert conv == "對方叫小明。"
    assert self_ == ""


def test_self_section_placeholder_variants_are_dropped():
    for placeholder in (
        "（目前沒有任何關於自己的記憶）",
        "（目前沒有關於自己的記憶）",
    ):
        text = (
            f"{SECTION_CONVERSATION}\n對方叫小明。\n"
            f"{self_section_label(NAME)}\n{placeholder}\n"
        )
        _, self_ = split_consolidation_output(text, NAME)
        assert self_ == ""


def test_conversation_section_with_only_placeholder_is_empty():
    text = (
        f"{SECTION_CONVERSATION}\n（目前還沒有任何記憶）\n"
        f"{self_section_label(NAME)}\n紅莉栖喜歡咖啡。\n"
    )
    conv, self_ = split_consolidation_output(text, NAME)
    assert conv == ""
    assert self_ == "紅莉栖喜歡咖啡。"


def test_parenthetical_only_line_dropped_among_real_lines():
    text = (
        f"{SECTION_CONVERSATION}\n對方叫小明。\n（沒有更多了）\n對方喜歡貓。\n"
        f"{self_section_label(NAME)}\n紅莉栖喜歡咖啡。\n"
    )
    conv, self_ = split_consolidation_output(text, NAME)
    assert conv == "對方叫小明。\n對方喜歡貓。"


def test_line_merely_containing_parentheses_is_kept():
    text = (
        f"{SECTION_CONVERSATION}\n紅莉栖喜歡咖啡（黑的）。\n"
        f"{self_section_label(NAME)}\n"
    )
    conv, self_ = split_consolidation_output(text, NAME)
    assert conv == "紅莉栖喜歡咖啡（黑的）。"


def test_filter_drops_lines_mentioning_the_other_party():
    text = "紅莉栖喜歡咖啡。\n紅莉栖和對方去過秋葉原。\n紅莉栖答應你下次帶書來。\n紅莉栖討厭夏天。"
    assert filter_self_lines(text) == "紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。"


def test_filter_keeps_everything_when_clean():
    text = "紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。"
    assert filter_self_lines(text) == text


def test_filter_on_empty_is_empty():
    assert filter_self_lines("") == ""
    assert filter_self_lines("\n\n") == ""


def _prompt(**kw):
    base = dict(
        current="對方叫小明。",
        user_input="今天好累",
        ai_response="辛苦了。",
        cap=1500,
        character_name=NAME,
        current_self="紅莉栖喜歡咖啡。",
    )
    base.update(kw)
    return build_consolidation_prompt(**base)


def test_prompt_asks_for_both_section_markers():
    p = _prompt()
    assert SECTION_CONVERSATION in p
    assert self_section_label(NAME) in p


def test_prompt_carries_both_existing_memories():
    p = _prompt()
    assert "對方叫小明。" in p
    assert "紅莉栖喜歡咖啡。" in p


def test_prompt_states_the_self_cap():
    assert str(SELF_CAP_CHARS) in _prompt()


def test_prompt_says_anything_involving_the_other_party_goes_to_conversation():
    # 這條是分類規則的核心：主詞是她但牽涉對方 → 對話記憶。用穩定關鍵詞釘住。
    p = _prompt()
    assert "牽涉到對方" in p


def test_prompt_keeps_the_old_subject_rules():
    # 既有測試 tests/test_memory_uses_in_world_subject.py 釘住這些字串，不能掉。
    p = _prompt()
    assert "「對方」或「紅莉栖」開頭" in p
    assert "使用者" not in p
    assert "拒絕" in p and "聽不" in p and "測試" in p


def test_prompt_placeholder_for_empty_self_memory():
    p = _prompt(current_self="")
    assert "（目前還沒有任何關於自己的記憶）" in p


def test_prompt_gives_a_standalone_test_for_self_classification():
    p = _prompt()
    assert "判斷方法" in p


def test_prompt_forbids_placeholder_text_when_a_section_is_empty():
    p = _prompt()
    assert "不要寫「目前還沒有」" in p
