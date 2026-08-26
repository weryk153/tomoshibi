"""跨輪的逐句防重複。

實測抓到的失敗模式：模型只換掉開頭四個字，正文整段照抄。

  [2] ……夠了。 *視線完全移開，盯著遠方路標…* 既然你這麼愛盯著我看…
  [3] ……沒變。 *視線完全移開，盯著遠方路標…* 既然你這麼愛盯著我看…

「整則比對」攔不到——開頭一分岔就當成不同的回覆。攔得到的是逐句比對：把最近
幾則回覆的句子當成護欄的初始狀態，重複的那幾句在送去 TTS 之前就被丟掉。
"""

from src.open_llm_vtuber.conversation_quality import (
    ResponseRepetitionGuard,
    deduplicate_response_text,
)
from src.open_llm_vtuber import reply_history


def setup_function():
    reply_history.reset_for_tests()


_BODY = "*視線完全移開，盯著遠方路標，手裡輕輕整理著衣領，語氣平淡卻帶著一絲不耐煩*"
_ASK = "既然你這麼愛盯著我看，不如幫我把這件外套上的汙漬清理掉？"


def test_a_fresh_guard_still_accepts_everything():
    # 沒有種子時行為不變——deduplicate_response_text 等既有呼叫端靠這個。
    guard = ResponseRepetitionGuard()
    assert guard.accept(_BODY)


def test_a_seeded_guard_rejects_what_was_said_last_turn():
    guard = ResponseRepetitionGuard(seen=[_BODY, _ASK])
    assert not guard.accept(_BODY), "上一輪講過的句子不該再送出去"
    assert not guard.accept(_ASK)


def test_a_seeded_guard_still_accepts_new_sentences():
    guard = ResponseRepetitionGuard(seen=[_BODY, _ASK])
    assert guard.accept("……不過北邊那座山今天看起來特別清楚，我們繞過去看看吧。")


def test_seeding_does_not_disturb_the_existing_dedup_helper():
    text = "第一句。第一句。第二句。"
    assert deduplicate_response_text(text) == "第一句。第二句。"


def test_recent_sentences_splits_stored_replies():
    reply_history.record_reply("c1", "h1", "u1", f"……夠了。{_BODY}{_ASK}")
    got = reply_history.recent_sentences("c1", "h1", "u1")
    assert any(_ASK in s for s in got), "整句要拆得出來才能逐句比對"
    assert len(got) >= 2


def test_recent_sentences_is_empty_when_nothing_was_said():
    assert reply_history.recent_sentences("c1", "h1", "u1") == []


def test_recent_sentences_is_per_session():
    reply_history.record_reply("c1", "h1", "u1", "第一句。第二句。")
    assert reply_history.recent_sentences("c1", "h1", "u2") == []


def test_recent_sentences_is_per_history_uid():
    # 同一條 WebSocket 連線（client_uid 不變）切換對話（history_uid 換了），
    # 上一段對話說過的話不該滲進新對話——這正是這次要補的外洩。
    reply_history.record_reply("c1", "h1", "u1", "上一段對話說的祕密。")
    assert reply_history.recent_sentences("c1", "h2", "u1") == []


def test_recent_sentences_is_empty_when_history_uid_is_missing():
    # history_uid 為空：不讀、不回退到只用 conf_uid+client_uid 的舊範圍。
    reply_history.record_reply("c1", "h1", "u1", "第一句。")
    assert reply_history.recent_sentences("c1", "", "u1") == []


def test_record_reply_does_not_write_when_history_uid_is_missing():
    # 空 history_uid 也不寫入——不然之後補上同一把 client_uid 的 history_uid
    # 時，會讀到一段沒有對話可歸屬的殘留狀態。
    reply_history.record_reply("c1", "", "u1", "沒有對話可歸屬的一句話。")
    assert reply_history.recent_sentences("c1", "h1", "u1") == []
