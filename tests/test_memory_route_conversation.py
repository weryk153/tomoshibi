"""設定頁的記憶端點要對「當前對話」作用。

conf_uid 前端知道（從 set-model-and-conf 來），history_uid 不知道——它活在每個
連線各自的 ServiceContext 裡。所以 route 要從連線取，取不到就回 409，不要猜一個：
猜錯會編輯到別段對話的記憶。
"""

from types import SimpleNamespace

from src.open_llm_vtuber import memory_route


def _ctx(conf_uid, history_uid):
    return SimpleNamespace(
        character_config=SimpleNamespace(conf_uid=conf_uid),
        history_uid=history_uid,
    )


def test_resolves_the_conversation_from_a_live_connection():
    contexts = {"client-1": _ctx("charA", "conv9")}
    assert memory_route._resolve_history_uid(contexts, "charA") == "conv9"


def test_ignores_connections_for_a_different_character():
    contexts = {"client-1": _ctx("charB", "conv9")}
    assert memory_route._resolve_history_uid(contexts, "charA") is None


def test_no_connection_means_no_conversation():
    assert memory_route._resolve_history_uid({}, "charA") is None


def test_a_connection_still_initialising_does_not_count():
    # history_uid 是空字串代表連線還在初始化，那不是一段可以編輯的對話。
    contexts = {"client-1": _ctx("charA", "")}
    assert memory_route._resolve_history_uid(contexts, "charA") is None


def test_takes_the_most_recent_connection():
    contexts = {
        "old": _ctx("charA", "conv1"),
        "new": _ctx("charA", "conv2"),
    }
    assert memory_route._resolve_history_uid(contexts, "charA") == "conv2"
