"""被擋掉的主動開口也要記進防重複清單，否則模型會一直重生同一句。

實測一段 44 輪主動開口的紀錄：

    句子被抑制      78 次
    整輪全被擋      24 輪（55%）
    記進防重複清單  16 次

有 28 輪最後什麼都沒說出口。原因是活鎖：

  1. 模型生出一句，被 should_suppress_proactive_text 擋下來。
  2. record_proactive_response 只在回覆「被接受」時才呼叫，所以這句沒進清單。
  3. 下一輪的提示詞用 get_recent_proactive 組出「最近已經主動說過的內容，不可重複」
     ——清單裡沒有那句，模型不知道自己剛講過。
  4. 於是再生一次同一句，再被擋。

被擋掉的句子正是最需要記下來別再講的那一句，現在偏偏只有它不會被記。

但它不能走 record_proactive_response：那個函式同時會把句子放進 _pending，而 _pending
是「使用者下次真的開口時，告訴角色她剛才說了什麼」的橋。被擋掉的句子從來沒有說出口，
放進去會讓角色以為自己講過。
"""

from src.open_llm_vtuber.proactive_context import (
    clear_proactive_context,
    consecutive_proactive_turns,
    consume_pending_proactive,
    get_recent_proactive,
    proactive_lines_since_user_turn,
    record_proactive_response,
    record_suppressed_proactive,
)

CONF = "char_test"
CLIENT = "client_test"


def setup_function() -> None:
    clear_proactive_context(CONF, CLIENT)


def teardown_function() -> None:
    clear_proactive_context(CONF, CLIENT)


def test_suppressed_line_reaches_the_anti_repeat_list():
    record_suppressed_proactive(CONF, CLIENT, "手好像有點抖。")

    assert "手好像有點抖。" in get_recent_proactive(CONF, CLIENT)


def test_suppressed_line_never_becomes_the_reply_bridge():
    # 這句從來沒說出口。放進 _pending 會讓角色在使用者下次開口時，以為自己講過。
    record_suppressed_proactive(CONF, CLIENT, "手好像有點抖。")

    assert consume_pending_proactive(CONF, CLIENT) is None


def test_accepted_line_still_becomes_the_reply_bridge():
    # 收窄不能傷到原本那條路。
    record_proactive_response(CONF, CLIENT, "前面那條小路草很深。")

    assert consume_pending_proactive(CONF, CLIENT) == "前面那條小路草很深。"


def test_suppressed_line_does_not_count_as_a_turn_she_spoke():
    # _since_user 有兩個消費者，兩個都把它當成「她說出口的話」：
    # consecutive_proactive_turns 決定要不要收手別再講，
    # proactive_lines_since_user_turn 餵給錨點當成她講過的內容。
    # 被擋掉的句子從來沒說出口，兩邊都不該看到它。
    record_suppressed_proactive(CONF, CLIENT, "手好像有點抖。")

    assert consecutive_proactive_turns(CONF, CLIENT) == 0
    assert proactive_lines_since_user_turn(CONF, CLIENT) == []


def test_accepted_line_does_count_as_a_turn_she_spoke():
    record_proactive_response(CONF, CLIENT, "前面那條小路草很深。")

    assert consecutive_proactive_turns(CONF, CLIENT) == 1


def test_blank_text_is_ignored():
    record_suppressed_proactive(CONF, CLIENT, "   ")

    assert get_recent_proactive(CONF, CLIENT) == []
