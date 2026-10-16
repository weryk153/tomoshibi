"""主動開口不照抄自己最近主動說過的話。

實測：連續主動開口時，第四次整句是「嘿嘿，開個玩笑啦。你要不要來看看？」，照抄第二次
的結尾。提示叫她換話題也擋不住，所以在主機這邊逐句擋。
"""

from src.open_llm_vtuber.proactive_context import repeats_recent

EARLIER = ["剛才在資料室看到一本新的漫畫，封面上的角色長得有點像你……嘿嘿，開個玩笑啦。你要不要來看看？"]


def test_a_sentence_she_already_said_proactively_is_a_repeat():
    assert repeats_recent("嘿嘿，開個玩笑啦。", EARLIER)
    assert repeats_recent("你要不要來看看？", EARLIER)


def test_punctuation_and_spacing_do_not_hide_a_repeat():
    assert repeats_recent("你 要不要來看看!!", EARLIER)


def test_a_short_interjection_is_not_a_repeat():
    assert not repeats_recent("嘿嘿！", EARLIER)
    assert not repeats_recent("好喔", EARLIER)


def test_a_new_sentence_is_not_a_repeat():
    assert not repeats_recent("我剛才在畫室試著畫了幾個新構圖。", EARLIER)
    assert not repeats_recent("你要不要來看看？", [])
