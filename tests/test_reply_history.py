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


def test_retry_prompt_names_the_repeated_line():
    prompt = reply_history.build_reply_retry_prompt("原本的提示", "你眼光真差。")
    assert "原本的提示" in prompt
    assert "你眼光真差。" in prompt


# --- 預防：把最近說過的幾則放進當輪上下文 ---


def test_no_guidance_when_nothing_was_said_yet():
    # 第一輪不該憑空多出一段「不要重複」——沒有東西可以重複。
    assert reply_history.build_recent_reply_guidance("c1", "h1", "u1") == ""


def test_guidance_lists_what_was_recently_said():
    reply_history.record_reply("c1", "h1", "u1", "你眼光真差。")
    reply_history.record_reply("c1", "h1", "u1", "別再說了。")
    g = reply_history.build_recent_reply_guidance("c1", "h1", "u1")
    assert "你眼光真差。" in g
    assert "別再說了。" in g


def test_guidance_is_per_session():
    reply_history.record_reply("c1", "h1", "u1", "你眼光真差。")
    assert reply_history.build_recent_reply_guidance("c1", "h1", "u2") == ""


def test_guidance_lists_newest_last():
    # 模型對結尾的內容最敏感，最近說過的那句要放在最後才擋得住。
    reply_history.record_reply("c1", "h1", "u1", "第一句。")
    reply_history.record_reply("c1", "h1", "u1", "第二句。")
    g = reply_history.build_recent_reply_guidance("c1", "h1", "u1")
    assert g.index("第一句。") < g.index("第二句。")


def test_guidance_caps_how_many_lines_it_lists():
    for i in range(reply_history.MAX_RECENT_REPLIES):
        reply_history.record_reply("c1", "h1", "u1", f"第 {i} 句。")
    g = reply_history.build_recent_reply_guidance("c1", "h1", "u1")
    assert g.count("\n- ") <= reply_history.MAX_GUIDANCE_LINES


# --- 隱私：state 跟著對話（history_uid）走，不是連線（client_uid）走 ---


def test_guidance_is_per_history_uid_even_with_same_client():
    # 同一條連線切換對話：上一段對話的內容不能滲進新對話的提示詞。這是這次
    # 要補的外洩本身——不是防禦性測試，是回歸測試。
    reply_history.record_reply("c1", "h1", "u1", "上一段對話說過的隱私。")
    g = reply_history.build_recent_reply_guidance("c1", "h2", "u1")
    assert "上一段對話說過的隱私。" not in g
    assert g == ""


def test_guidance_is_empty_when_history_uid_is_missing():
    # 空 history_uid：不讀、也不要回退到只用 conf_uid+client_uid 的舊範圍。
    reply_history.record_reply("c1", "h1", "u1", "你眼光真差。")
    assert reply_history.build_recent_reply_guidance("c1", "", "u1") == ""
