"""同一段對話有多台裝置連著時，誰負責主動發言。

主動發言的閒置計時器在前端，每個連線各有一個。兩台同時開著時兩邊都會送
ai-speak-signal，於是角色各講各的：兩台畫面上的內容不一樣，而且兩句都被寫進
同一段對話，讀起來像她在自言自語。

規則是「最近使用過的那台」負責。你剛在手機上打完字，主動發言就該從手機發生，
而不是從你早就沒在看的桌機。發話端講的話會透過 history 推送同步到另一台，所以
限制成一台不會讓另一台漏掉內容——反而是唯一能讓兩邊一致的做法。
"""

from types import SimpleNamespace

from src.open_llm_vtuber.websocket_handler import is_proactive_owner


def _ctx(conf_uid: str, history_uid: str | None):
    return SimpleNamespace(
        character_config=SimpleNamespace(conf_uid=conf_uid),
        history_uid=history_uid,
    )


def test_single_client_owns_it():
    contexts = {"pc": _ctx("frieren", "h1")}
    assert is_proactive_owner(contexts, {"pc": 100.0}, "pc") is True


def test_most_recently_active_client_wins():
    contexts = {"pc": _ctx("frieren", "h1"), "phone": _ctx("frieren", "h1")}
    last = {"pc": 100.0, "phone": 200.0}
    assert is_proactive_owner(contexts, last, "phone") is True
    assert is_proactive_owner(contexts, last, "pc") is False


def test_clients_on_other_conversations_do_not_compete():
    # 另一台在翻舊對話，不該因為它比較新就把這段的主動發言搶走。
    contexts = {"pc": _ctx("frieren", "h1"), "other": _ctx("frieren", "h-old")}
    last = {"pc": 100.0, "other": 999.0}
    assert is_proactive_owner(contexts, last, "pc") is True


def test_clients_on_other_characters_do_not_compete():
    contexts = {"pc": _ctx("frieren", "h1"), "other": _ctx("kurisu", "h1")}
    last = {"pc": 100.0, "other": 999.0}
    assert is_proactive_owner(contexts, last, "pc") is True


def test_a_tie_still_picks_exactly_one():
    # 兩台同時連上、都還沒講過話時時間戳會一樣。沒有決勝規則的話兩台都會認為
    # 自己是負責的，等於沒修。
    contexts = {"aaa": _ctx("frieren", "h1"), "bbb": _ctx("frieren", "h1")}
    last = {"aaa": 100.0, "bbb": 100.0}
    owners = [uid for uid in ("aaa", "bbb") if is_proactive_owner(contexts, last, uid)]
    assert len(owners) == 1


def test_missing_activity_entry_counts_as_never_active():
    contexts = {"pc": _ctx("frieren", "h1"), "phone": _ctx("frieren", "h1")}
    assert is_proactive_owner(contexts, {"pc": 100.0}, "pc") is True
    assert is_proactive_owner(contexts, {"pc": 100.0}, "phone") is False


def test_unknown_client_is_not_the_owner():
    assert (
        is_proactive_owner({"pc": _ctx("frieren", "h1")}, {"pc": 1.0}, "gone") is False
    )


def test_client_with_no_conversation_is_not_the_owner():
    # 還沒開始任何對話的連線不該主動開口。
    contexts = {"pc": _ctx("frieren", None)}
    assert is_proactive_owner(contexts, {"pc": 100.0}, "pc") is False
