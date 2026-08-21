"""一般回覆的跨輪重複防護。

single_conversation 每一輪都新建一個 ResponseRepetitionGuard，所以它只看得到
「同一則回覆裡的句子」。三則不同的使用者訊息各自得到逐字相同的回覆時，沒有
任何東西擋得住——實際發生過：「……是嗎？*不自覺地摸了摸臉頰……*  你眼光真差。」
連續四次。

主動發言那條路早就有跨輪記錄（proactive_context），這個模組是一般回覆的對應物。
"""

from src.open_llm_vtuber import reply_history


def setup_function():
    reply_history.reset_for_tests()


def test_a_reply_is_not_a_repeat_the_first_time():
    assert not reply_history.is_repeat_of_recent("c1", "u1", "你眼光真差。")


def test_the_same_reply_next_turn_is_a_repeat():
    reply_history.record_reply("c1", "u1", "你眼光真差。")
    assert reply_history.is_repeat_of_recent("c1", "u1", "你眼光真差。")


def test_whitespace_differences_still_count_as_the_same():
    # 串流拼出來的文字，空白與換行位置會漂移；那不算不同的回覆。
    reply_history.record_reply("c1", "u1", "你眼光真差。")
    assert reply_history.is_repeat_of_recent("c1", "u1", "  你眼光真差。\n ")


def test_a_different_reply_is_not_a_repeat():
    reply_history.record_reply("c1", "u1", "你眼光真差。")
    assert not reply_history.is_repeat_of_recent("c1", "u1", "隨你怎麼說。")


def test_sessions_do_not_leak_into_each_other():
    reply_history.record_reply("c1", "u1", "你眼光真差。")
    assert not reply_history.is_repeat_of_recent("c1", "u2", "你眼光真差。")
    assert not reply_history.is_repeat_of_recent("c2", "u1", "你眼光真差。")


def test_only_the_recent_window_is_remembered():
    for i in range(reply_history.MAX_RECENT_REPLIES + 1):
        reply_history.record_reply("c1", "u1", f"第 {i} 句。")
    # 最舊的那句已經被擠掉，再說一次不算重複。
    assert not reply_history.is_repeat_of_recent("c1", "u1", "第 0 句。")
    assert reply_history.is_repeat_of_recent("c1", "u1", "第 1 句。")


def test_blank_replies_are_not_recorded():
    reply_history.record_reply("c1", "u1", "   \n  ")
    assert not reply_history.is_repeat_of_recent("c1", "u1", "")


def test_retry_prompt_names_the_repeated_line():
    prompt = reply_history.build_reply_retry_prompt("原本的提示", "你眼光真差。")
    assert "原本的提示" in prompt
    assert "你眼光真差。" in prompt


# --- 推測性緩衝：串流當下就要判斷「還有可能是重複嗎」 ---


def test_an_empty_buffer_is_not_treated_as_a_prefix():
    # 空字串是任何字串的開頭。若當成「可能重複」，每一輪的第一句都會被無故
    # 緩衝，等於把零延遲的前提毀掉。
    reply_history.record_reply("c1", "u1", "……是嗎？你眼光真差。")
    assert not reply_history.prefix_matches_recent("c1", "u1", "")


def test_nothing_recorded_means_nothing_to_match():
    assert not reply_history.prefix_matches_recent("c1", "u1", "……是嗎？")


# --- ReplyBuffer：串流當下決定每一句先扣住還是直接放行 ---


def _buffer(**kw):
    return reply_history.ReplyBuffer("c1", "u1", **kw)


def test_with_no_history_every_sentence_goes_straight_out():
    buf = _buffer()
    assert buf.offer("A", "第一句。") == ["A"]
    assert buf.offer("B", "第二句。") == ["B"]
    assert buf.flush() == []


def test_disabled_buffer_never_holds_anything():
    # 主動發言那條路自己有一套跨輪機制，不要兩層互相打架。
    reply_history.record_reply("c1", "u1", "……是嗎？你眼光真差。")
    buf = _buffer(enabled=False)
    assert buf.offer("A", "……是嗎？") == ["A"]
    assert not buf.is_full_repeat


# --- 預防：把最近說過的幾則放進當輪上下文 ---


def test_no_guidance_when_nothing_was_said_yet():
    # 第一輪不該憑空多出一段「不要重複」——沒有東西可以重複。
    assert reply_history.build_recent_reply_guidance("c1", "u1") == ""


def test_guidance_lists_what_was_recently_said():
    reply_history.record_reply("c1", "u1", "你眼光真差。")
    reply_history.record_reply("c1", "u1", "別再說了。")
    g = reply_history.build_recent_reply_guidance("c1", "u1")
    assert "你眼光真差。" in g
    assert "別再說了。" in g


def test_guidance_is_per_session():
    reply_history.record_reply("c1", "u1", "你眼光真差。")
    assert reply_history.build_recent_reply_guidance("c1", "u2") == ""


def test_guidance_lists_newest_last():
    # 模型對結尾的內容最敏感，最近說過的那句要放在最後才擋得住。
    reply_history.record_reply("c1", "u1", "第一句。")
    reply_history.record_reply("c1", "u1", "第二句。")
    g = reply_history.build_recent_reply_guidance("c1", "u1")
    assert g.index("第一句。") < g.index("第二句。")


def test_guidance_caps_how_many_lines_it_lists():
    for i in range(reply_history.MAX_RECENT_REPLIES):
        reply_history.record_reply("c1", "u1", f"第 {i} 句。")
    g = reply_history.build_recent_reply_guidance("c1", "u1")
    assert g.count("\n- ") <= reply_history.MAX_GUIDANCE_LINES


# --- 改用相似度：只差兩三個字的重複也要擋 ---

_R3 = "……是嗎？*眼神完全移開，盯著魔導書上某個不起眼的符號，連耳朵都似乎不自覺地聳了一下* 既然你這麼堅持說我有問題，那不如來猜猜看，我剛才那招的魔法，到底是用哪種材料調變的比較有效？"
_R4 = "……是嗎？*視線完全移開，盯著魔導書上某個不起眼的符號，連耳朵都似乎不自覺地聳了一下* 既然你這麼堅持說我有問題，那不如來猜猜看，我剛才那招的魔法，到底是用哪種材料調變的比較有效？"


def test_a_near_duplicate_counts_as_a_repeat():
    # 實測抓到的真實案例：整句只差「眼神」/「視線」兩個字。逐字比對放它過去，
    # 但人一看就是同一句。
    reply_history.record_reply("c1", "u1", _R3)
    assert reply_history.is_repeat_of_recent("c1", "u1", _R4)


def test_a_genuinely_different_reply_is_still_allowed():
    reply_history.record_reply("c1", "u1", _R3)
    assert not reply_history.is_repeat_of_recent(
        "c1", "u1", "今天天氣不錯，我們出去走走吧。"
    )


def test_a_short_opening_still_holds_when_it_matches_exactly():
    # 句子切分器會在「？」斷句，所以第一段常常只有「……是嗎？」五個字。這裡
    # 若不扣住，整個機制就等於關閉——實測過，一次都攔不到。太短時改用嚴格的
    # 逐字開頭比對：夠保守，又不會讓機制失效。
    reply_history.record_reply("c1", "u1", _R3)
    assert reply_history.prefix_matches_recent("c1", "u1", "……是嗎？")


def test_a_short_opening_that_matches_nothing_is_released():
    reply_history.record_reply("c1", "u1", _R3)
    assert not reply_history.prefix_matches_recent("c1", "u1", "今天天氣")


def test_a_long_near_identical_opening_is_held():
    reply_history.record_reply("c1", "u1", _R3)
    assert reply_history.prefix_matches_recent("c1", "u1", _R4[:40])


def test_a_long_opening_that_really_differs_is_released():
    reply_history.record_reply("c1", "u1", _R3)
    assert not reply_history.prefix_matches_recent(
        "c1", "u1", "……我累了，不想再談這個話題了，我們往北邊走吧，費倫他們應該在等。"
    )


# 以下用實際長度的句子。角色的起手式很短又常重複，所以緩衝只在累積夠長之後
# 才開始判斷——短句餵進來什麼都不會被扣住，那是刻意的取捨。

_HEAD = "……是嗎？*視線完全移開，盯著魔導書上某個不起眼的符號，連耳朵都不自覺地聳了一下*"
_TAIL = "既然你這麼堅持說我有問題，那不如來猜猜看答案。"
_FULL = _HEAD + _TAIL


def test_a_long_matching_opening_is_held_back():
    reply_history.record_reply("c1", "u1", _FULL)
    buf = _buffer()
    assert buf.offer("A", _HEAD) == [], "還可能是重複，先不要送去 TTS"


def test_everything_held_is_released_the_moment_it_diverges():
    reply_history.record_reply("c1", "u1", _FULL)
    buf = _buffer()
    buf.offer("A", _HEAD)
    released = buf.offer("B", "不過這次我想講點別的，關於北邊那座山的事情。")
    assert released == ["A", "B"], "分岔時先前扣住的要照原順序一起放行"
    assert buf.offer("C", "第三句。") == ["C"], "分岔之後就不再緩衝"


def test_an_exact_repeat_is_recognised_at_the_end():
    reply_history.record_reply("c1", "u1", _FULL)
    buf = _buffer()
    buf.offer("A", _HEAD)
    buf.offer("B", _TAIL)
    assert buf.is_full_repeat
    assert buf.held_text == _FULL


def test_a_shorter_reply_that_never_diverged_is_still_spoken():
    # 新回覆剛好是舊回覆的開頭（更短）。它不是重複，不能被吞掉——否則她會沈默。
    reply_history.record_reply("c1", "u1", _FULL)
    buf = _buffer()
    buf.offer("A", _HEAD)
    assert not buf.is_full_repeat
    assert buf.flush() == ["A"]


def test_disabled_buffer_never_holds_anything():
    # 主動發言那條路自己有一套跨輪機制，不要兩層互相打架。
    reply_history.record_reply("c1", "u1", _FULL)
    buf = _buffer(enabled=False)
    assert buf.offer("A", _HEAD) == ["A"]
    assert not buf.is_full_repeat
