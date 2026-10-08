"""「你沒回話時：等你」——主動開口沒人回就一次比一次等得久，連續 3 次就停。

前端照設定的秒數一直送觸發；要不要開口由後端照這個角色的設定決定。
"""

from src.open_llm_vtuber.proactive_context import wait_allows_speaking


def test_she_speaks_on_the_first_trigger_when_nobody_owes_her_an_answer():
    assert wait_allows_speaking(("k", "c"), unanswered=0)


def test_each_unanswered_remark_doubles_the_wait_and_three_stop_her():
    key = ("kurisu", "client-a")
    # 沒回 1 次：等 2 倍（跳過 1 次觸發）；沒回 2 次：等 4 倍（跳過 3 次）。
    assert [wait_allows_speaking(key, 1) for _ in range(2)] == [False, True]
    assert [wait_allows_speaking(key, 2) for _ in range(4)] == [
        False,
        False,
        False,
        True,
    ]
    assert not any(wait_allows_speaking(key, 3) for _ in range(20))


def test_when_the_user_answers_she_starts_over():
    key = ("kurisu", "client-b")
    assert not wait_allows_speaking(key, 1)
    assert wait_allows_speaking(key, 0)
    assert not wait_allows_speaking(key, 1)  # 重新算，不沿用之前跳過的次數


def test_only_a_character_set_to_wait_skips_triggers():
    from types import SimpleNamespace

    from src.open_llm_vtuber.conversations.conversation_handler import _speaks_up_now

    def context(mode, unanswered):
        return SimpleNamespace(
            character_config=SimpleNamespace(
                conf_uid="m7", proactive_when_unanswered=mode
            ),
            agent_engine=SimpleNamespace(unanswered_remarks=lambda uid: unanswered),
            history_uid="h1",
        )

    assert all(_speaks_up_now(context("keep_talking", 5), "c") for _ in range(5))
    assert not _speaks_up_now(context("wait", 3), "c")
    assert [_speaks_up_now(context("wait", 1), "d") for _ in range(2)] == [False, True]
