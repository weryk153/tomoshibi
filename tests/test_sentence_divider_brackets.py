r"""控制標籤帶強度之後，斷句器不能切在標籤中間。

`[joy:0.6]` 裡的小數點會被當成句號，把一句話切成 `[joy:0.` 和 `6] 哈哈`。
兩半的方括號都不成對，於是：

- 清理標籤的正規式 `\[[^\]]*\]` 比對不到 → 關鍵字原樣留在字幕與聊天紀錄上
- actions_extractor 也抽不到 → 表情與動作完全不會觸發

實際踩到過（`[joy:0.6] 哈哈，你怎麼一直催我笑啊！`）。
"""

import pytest

from src.open_llm_vtuber.utils.sentence_divider import (
    has_unclosed_bracket,
    is_complete_sentence,
    segment_text_by_pysbd,
    segment_text_by_regex,
)

TAGGED = "[joy:0.6] 哈哈，你怎麼一直催我笑啊！"


@pytest.mark.parametrize("segment", [segment_text_by_regex, segment_text_by_pysbd])
def test_帶強度的標籤不會被小數點切開(segment):
    sentences, remaining = segment(TAGGED)
    assert sentences == [TAGGED], f"標籤被切開了：{sentences}"
    assert remaining == ""


@pytest.mark.parametrize("segment", [segment_text_by_regex, segment_text_by_pysbd])
def test_兩句各自帶標籤仍然正常斷句(segment):
    sentences, _ = segment("[joy:0.6] 第一句。[act_jump:0.4] 第二句！")
    assert sentences == ["[joy:0.6] 第一句。", "[act_jump:0.4] 第二句！"]


@pytest.mark.parametrize("segment", [segment_text_by_regex, segment_text_by_pysbd])
def test_沒有標籤時斷句行為不變(segment):
    sentences, _ = segment("好喔。笑就笑！")
    assert sentences == ["好喔。", "笑就笑！"]


def test_串流中標籤還沒收尾就不算完整句():
    # 只收到半個標籤時要繼續等，不能當成一句送出去
    assert is_complete_sentence("[joy:0.") is False
    assert is_complete_sentence("[joy:0.6] 哈哈！") is True


def test_一般小數點不會被誤判成未收尾標籤():
    assert has_unclosed_bracket("It costs 3.5 dollars.") is False
    assert has_unclosed_bracket("[joy:0.") is True
    assert has_unclosed_bracket("[joy:0.6]") is False
