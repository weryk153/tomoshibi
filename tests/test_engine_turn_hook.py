"""一輪講完後通知 agent（character_engine/turn_hook.py）。

single_conversation 在排記憶整理的同一個位置呼叫它。條件也跟記憶整理一樣：主動
發話與空輸入不算一輪。任何 agent 都可以被傳進來——沒有 observe_turn 的就跳過。
"""

from src.open_llm_vtuber.character_engine.turn_hook import notify_turn_finished


class Observer:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.seen = []

    def observe_turn(self, conf_uid, history_uid, user_text, reply):
        if self.fail:
            raise RuntimeError("engine is down")
        self.seen.append((conf_uid, history_uid, user_text, reply))


def notify(agent, **overrides):
    arguments = {
        "conf_uid": "kurisu",
        "history_uid": "h1",
        "user_text": "謝謝你",
        "reply": "不用謝啦。",
        "is_proactive": False,
    }
    arguments.update(overrides)
    notify_turn_finished(agent, **arguments)


def test_a_real_turn_is_passed_on():
    agent = Observer()

    notify(agent)

    assert agent.seen == [("kurisu", "h1", "謝謝你", "不用謝啦。")]


def test_agents_that_do_not_observe_are_left_alone():
    notify(object())
    notify(None)


def test_proactive_speech_is_not_a_turn():
    agent = Observer()

    notify(agent, is_proactive=True)

    assert agent.seen == []


def test_turns_with_nothing_said_are_skipped():
    agent = Observer()

    notify(agent, user_text="  ")
    notify(agent, reply="")
    notify(agent, user_text=None)
    notify(agent, history_uid="")

    assert agent.seen == []


def test_a_failing_observer_never_breaks_the_conversation():
    notify(Observer(fail=True))
