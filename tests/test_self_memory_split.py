"""整理 LLM 輸出的單一清單，逐行分類成 (對話記憶, 她自己的)。

分類由程式做，不靠模型：9B 模型在三輪 5×5 實測裡做不到穩定的兩段輸出
（0/25 → 0/25 → 11/25，且第三輪出現幻覺自我事實）。分不清的一律留在對話
記憶——那一邊是私人的，放錯不會外洩。
"""

from src.open_llm_vtuber.memory_core import (
    SELF_CAP_CHARS,
    build_consolidation_prompt,
    classify_memory_lines,
)

NAME = "紅莉栖"


def test_name_prefixed_line_without_the_other_party_is_self():
    conv, self_ = classify_memory_lines("紅莉栖喜歡咖啡。", NAME)
    assert conv == ""
    assert self_ == "紅莉栖喜歡咖啡。"


def test_name_prefixed_line_mentioning_the_other_party_is_conversation():
    conv, self_ = classify_memory_lines("紅莉栖和對方去過秋葉原。", NAME)
    assert conv == "紅莉栖和對方去過秋葉原。"
    assert self_ == ""


def test_name_prefixed_line_containing_ni_is_conversation():
    conv, self_ = classify_memory_lines("紅莉栖答應你下次帶書來。", NAME)
    assert conv == "紅莉栖答應你下次帶書來。"
    assert self_ == ""


def test_line_starting_with_the_other_party_is_conversation():
    conv, self_ = classify_memory_lines("對方叫小明。", NAME)
    assert conv == "對方叫小明。"
    assert self_ == ""


def test_line_without_a_clear_subject_is_conversation():
    conv, self_ = classify_memory_lines("喜歡安靜的氛圍。", NAME)
    assert conv == "喜歡安靜的氛圍。"
    assert self_ == ""


def test_list_prefixes_are_stripped_before_classifying():
    for prefix in ("- ", "• ", "・ "):
        conv, self_ = classify_memory_lines(f"{prefix}紅莉栖喜歡咖啡。", NAME)
        assert self_ == "紅莉栖喜歡咖啡。", prefix
        assert conv == ""


def test_pure_parenthetical_lines_are_dropped_from_both():
    for line in ("（目前還沒有任何記憶）", "（空）"):
        conv, self_ = classify_memory_lines(line, NAME)
        assert conv == ""
        assert self_ == ""


def test_line_merely_containing_parentheses_is_kept():
    conv, self_ = classify_memory_lines("紅莉栖喜歡咖啡（黑的）。", NAME)
    assert self_ == "紅莉栖喜歡咖啡（黑的）。"
    assert conv == ""


def test_empty_string_yields_two_empty_strings():
    assert classify_memory_lines("", NAME) == ("", "")


def test_empty_character_name_sends_everything_to_conversation():
    text = "紅莉栖喜歡咖啡。\n對方叫小明。"
    conv, self_ = classify_memory_lines(text, "")
    assert conv == text
    assert self_ == ""


def test_mixed_input_preserves_order_within_each_bucket():
    text = "紅莉栖喜歡咖啡。\n對方叫小明。\n紅莉栖討厭夏天。\n對方喜歡貓。"
    conv, self_ = classify_memory_lines(text, NAME)
    assert conv == "對方叫小明。\n對方喜歡貓。"
    assert self_ == "紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。"


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


def test_prompt_has_no_two_section_markers():
    # 兩段格式的殘留（【對話記憶】／【<name>自己】）不該再出現。
    assert "【" not in _prompt()


def test_prompt_has_no_placeholder_text_for_empty_memories():
    p = _prompt(current="", current_self="")
    assert "（目前還沒有任何記憶）" not in p
    assert "（目前還沒有任何關於自己的記憶）" not in p


def test_current_self_lines_precede_current_lines():
    p = _prompt(current="對方叫小明。", current_self="紅莉栖喜歡咖啡。")
    assert p.index("紅莉栖喜歡咖啡。") < p.index("對方叫小明。")


def test_prompt_states_the_combined_cap():
    p = _prompt(cap=1500)
    assert str(1500 + SELF_CAP_CHARS) in p


def test_prompt_keeps_the_old_subject_rules():
    # 既有測試（test_memory_uses_in_world_subject.py 等）釘住這些字串，不能掉。
    p = _prompt()
    assert "「對方」或「紅莉栖」開頭" in p
    assert "使用者" not in p
    assert "拒絕" in p
    assert "聽不" in p
    assert "測試" in p
    assert "主詞" in p
