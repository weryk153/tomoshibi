"""記憶整理節奏的計數器要跟著對話走，而且要有界。

背景：_TURN_COUNTS 原本只用 (conf_uid, client_uid) 當 key。client_uid 認的是
WebSocket 連線，不是對話——同一條連線裡切換對話（不重新連線）時，輪數計數
原封不動跟過去。整理間隔設 5 的話：四輪私聊後開新對話，新對話會在自己的
第一輪就整理（沿用了舊對話累積的計數），第二到五輪反而不整理。內容不會外洩
（consolidate_core_memory 本身帶的是正確的 context.history_uid），但節奏跟著
連線走而不是跟著對話走，是同一種漏洞形狀的又一次。

修法是把 history_uid 併進 key（緊跟在 conf_uid 之後，這個分支的慣例），並且
仿照 reply_history.py 的 OrderedDict + LRU 上限，避免一個瀏覽器分頁不斷切換
對話時這個 dict 無限增生。
"""

import pytest

from src.open_llm_vtuber.conversations import single_conversation as sc


@pytest.fixture(autouse=True)
def _clean_turn_counts():
    sc._TURN_COUNTS.clear()
    yield
    sc._TURN_COUNTS.clear()


def test_key_shape_is_conf_then_history_then_client():
    key = ("charA", "conv1", "client1")
    n = sc._bump_turn_count(key)
    assert n == 1
    assert list(sc._TURN_COUNTS.keys()) == [key]


def test_switching_conversation_does_not_inherit_the_old_count():
    conf_uid, client_uid = "charA", "client1"

    for _ in range(4):
        sc._bump_turn_count((conf_uid, "conv1", client_uid))
    assert sc._TURN_COUNTS[(conf_uid, "conv1", client_uid)] == 4

    # Same connection, new conversation: must start its own count at 1, not
    # continue from the old conversation's 4.
    n = sc._bump_turn_count((conf_uid, "conv2", client_uid))
    assert n == 1
    # The old conversation's count is untouched.
    assert sc._TURN_COUNTS[(conf_uid, "conv1", client_uid)] == 4


def test_dict_is_bounded_like_reply_history():
    for i in range(sc.MAX_TURN_COUNT_SESSIONS + 5):
        sc._bump_turn_count(("charA", f"conv{i}", "client1"))

    assert len(sc._TURN_COUNTS) == sc.MAX_TURN_COUNT_SESSIONS
    # The earliest sessions were evicted (LRU on insertion order).
    assert ("charA", "conv0", "client1") not in sc._TURN_COUNTS
    # The most recent ones survive.
    last = sc.MAX_TURN_COUNT_SESSIONS + 4
    assert ("charA", f"conv{last}", "client1") in sc._TURN_COUNTS


def test_touching_an_existing_key_keeps_it_alive_under_pressure():
    # Fill up to the cap.
    for i in range(sc.MAX_TURN_COUNT_SESSIONS):
        sc._bump_turn_count(("charA", f"conv{i}", "client1"))

    # Re-touch the oldest key so it should NOT be the next one evicted.
    oldest_key = ("charA", "conv0", "client1")
    sc._bump_turn_count(oldest_key)

    # Push one brand new key past the cap.
    sc._bump_turn_count(("charA", "conv-new", "client1"))

    assert oldest_key in sc._TURN_COUNTS
    # The second-oldest (never re-touched) is the one that got evicted.
    assert ("charA", "conv1", "client1") not in sc._TURN_COUNTS
