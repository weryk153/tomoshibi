"""一輪對話結束後，要把更新後的紀錄推給哪些其他連線。

兩台裝置（桌機 + 手機）連同一個角色時看的是同一段對話——後端在連線時還原的是
依角色存的 active history uid，不分裝置。但單人對話的回覆只送給發話的那個連線，
所以另一台要重整才看得到，兩台同時開著卻看不到彼此。

挑選對象的規則抽出來測：推錯人的後果是把 A 的對話內容送到正在看別段對話（或
別的角色）的 B 畫面上，等於當著使用者的面把他的畫面換掉。
"""

from types import SimpleNamespace

from src.open_llm_vtuber.websocket_handler import select_history_peers


def _ctx(conf_uid: str, history_uid: str | None):
    return SimpleNamespace(
        character_config=SimpleNamespace(conf_uid=conf_uid),
        history_uid=history_uid,
    )


def test_picks_other_clients_on_the_same_conversation():
    contexts = {
        "pc": _ctx("frieren", "hist-1"),
        "phone": _ctx("frieren", "hist-1"),
    }
    assert select_history_peers(contexts, "pc") == ["phone"]


def test_never_includes_the_client_that_just_spoke():
    # 發話端自己已經是即時串流收到的，再推一次會讓畫面重刷一遍。
    contexts = {"pc": _ctx("frieren", "hist-1")}
    assert select_history_peers(contexts, "pc") == []


def test_skips_clients_on_a_different_character():
    contexts = {
        "pc": _ctx("frieren", "hist-1"),
        "other": _ctx("aoi", "hist-1"),
    }
    assert select_history_peers(contexts, "pc") == []


def test_skips_clients_viewing_a_different_conversation():
    # 對方正在翻舊的對話，把當前這段推過去等於把他的畫面換掉。
    contexts = {
        "pc": _ctx("frieren", "hist-1"),
        "other": _ctx("frieren", "hist-old"),
    }
    assert select_history_peers(contexts, "pc") == []


def test_skips_clients_with_no_conversation_open():
    contexts = {
        "pc": _ctx("frieren", "hist-1"),
        "other": _ctx("frieren", None),
    }
    assert select_history_peers(contexts, "pc") == []


def test_no_peers_when_the_speaker_has_no_conversation():
    # 沒有 history_uid 就沒有東西可推，也不該把所有人都當成同一段。
    contexts = {
        "pc": _ctx("frieren", None),
        "other": _ctx("frieren", None),
    }
    assert select_history_peers(contexts, "pc") == []


def test_unknown_origin_client_yields_nothing():
    assert select_history_peers({"phone": _ctx("frieren", "hist-1")}, "gone") == []


def test_returns_every_matching_peer():
    contexts = {
        "pc": _ctx("frieren", "hist-1"),
        "phone": _ctx("frieren", "hist-1"),
        "tablet": _ctx("frieren", "hist-1"),
    }
    assert sorted(select_history_peers(contexts, "pc")) == ["phone", "tablet"]
