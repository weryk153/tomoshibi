"""認知工作階段（character_engine/session.py）：把每一輪交給引擎、提交結果、存檔。

背景模型全部用假的——這裡驗的是 Tomoshibi 怎麼用引擎（提交、改掛的界限、存檔、
失敗不外漏），不是模型寫得好不好。模型的部分靠真實模型的逐字稿人讀對照。

沒裝引擎的環境（Python 3.10 的預設安裝）整個檔案略過。
"""

import asyncio
import json
import re

import pytest

pytest.importorskip("ai_character_engine")

from ai_character_engine.llm.models import LLMResponse  # noqa: E402

from src.open_llm_vtuber.character_engine.session import (  # noqa: E402
    CognitionSession,
    CognitionSettings,
)

WARM = {
    "emotion": "開心",
    "intensity": 1.0,
    "valence": 0.9,
    "stance": 1.0,
    "confidence": 1.0,
    "evidence": ["謝謝你"],
}


NEUTRAL = {**WARM, "emotion": "平靜", "valence": 0.0, "stance": 0.0, "evidence": []}


def warm_only_when_thanked(messages):
    """同一個模型、不同輪次給不同答案：晚到的那一筆才分得出來有沒有被用上。"""
    thanked = "Latest event/user content:\n謝謝你昨天陪我" in messages[1].content
    return WARM if thanked else NEUTRAL


class Worker:
    """回傳固定 JSON 的背景模型。payload 可以是函式，拿得到引擎送來的訊息。"""

    # 所有假模型共用：同一時間有幾個在跑、依序是誰跑的。真實情況是同一顆本機模型。
    running = 0
    most_at_once = 0
    order = []

    def __init__(self, payload, *, gate=None, fail=False, name=""):
        self.payload = payload
        self.gate = gate
        self.fail = fail
        self.name = name
        self.calls = 0
        self.abandoned = 0

    @classmethod
    def reset(cls):
        cls.running, cls.most_at_once, cls.order = 0, 0, []

    async def generate(self, messages, *, tools=None):
        self.calls += 1
        Worker.order.append(self.name)
        Worker.running += 1
        Worker.most_at_once = max(Worker.most_at_once, Worker.running)
        try:
            if self.gate is not None:
                await self.gate.wait()
            await asyncio.sleep(0)
            if self.fail:
                raise RuntimeError("model is down")
            payload = self.payload(messages) if callable(self.payload) else self.payload
            return LLMResponse(
                text=json.dumps(payload, ensure_ascii=False), model="fake"
            )
        except asyncio.CancelledError:
            self.abandoned += 1
            raise
        finally:
            Worker.running -= 1


def session(tmp_path, workers, **settings):
    defaults = {
        "emotion_every": 0,
        "memory_every": 0,
        "summary_every": 0,
        "reflection_every": 0,
        "goal_every": 0,
    }
    defaults.update(settings)
    return CognitionSession(
        storage_dir=tmp_path / "engine",
        character_id="kurisu",
        character_name="紅莉栖",
        client_for_role=workers.get,
        settings=CognitionSettings(**defaults),
    )


def run(coroutine):
    Worker.reset()
    return asyncio.run(coroutine)


def test_every_recorded_turn_builds_trust_and_survives_a_restart(tmp_path):
    async def scenario():
        first = session(tmp_path, {})
        first.bind_conversation("h1", [])
        await first.observe_turn("你好", "嗯，你好。")
        await first.observe_turn("今天天氣不錯", "是啊。")
        await first.close()

        reopened = session(tmp_path, {})
        return reopened.snapshot()

    assert run(scenario()).trust == pytest.approx(50.6)


def test_a_warm_turn_lifts_her_mood_before_the_next_turn_starts(tmp_path):
    async def scenario():
        current = session(tmp_path, {"emotion": Worker(WARM)}, emotion_every=1)
        current.bind_conversation("h1", [])
        await current.observe_turn("謝謝你昨天陪我", "不、不用謝啦。")
        await current.settle()
        snapshot = current.snapshot()
        await current.close()
        return snapshot

    snapshot = run(scenario())
    assert snapshot.emotion == "happy"
    assert snapshot.favorability == pytest.approx(54.0)
    assert snapshot.trust == pytest.approx(50.3 + 2.0)


def test_a_late_result_is_used_when_nothing_newer_of_its_kind_is_coming(tmp_path):
    """情緒每兩輪分析一次：第 2 輪的結果在第 3 輪才回來，而第 3 輪沒有排新的
    情緒分析，所以這一筆仍然是最新的觀察。"""

    async def scenario():
        gate = asyncio.Event()
        worker = Worker(warm_only_when_thanked, gate=gate)
        current = session(
            tmp_path, {"emotion": worker}, emotion_every=2, max_rebase_turns=3
        )
        current.bind_conversation("h1", [])
        await current.observe_turn("嗨", "嗯。")
        await current.observe_turn("謝謝你昨天陪我", "不用謝。")
        while worker.calls == 0:
            await asyncio.sleep(0)
        await current.observe_turn("對了", "嗯？")
        gate.set()
        await current.settle()
        snapshot = current.snapshot()
        await current.close()
        return snapshot

    assert run(scenario()).favorability == pytest.approx(54.0)


def test_a_late_result_gives_way_to_a_newer_one_of_its_kind(tmp_path):
    """情緒每輪都分析：第 1 輪的結果回來時第 2 輪已經排了新的。引擎每個版本只收
    一筆情緒觀察，舊的搶先佔位的話新的會被判成衝突——所以舊的讓路。"""

    async def scenario():
        gate = asyncio.Event()
        worker = Worker(warm_only_when_thanked, gate=gate)
        current = session(
            tmp_path, {"emotion": worker}, emotion_every=1, max_rebase_turns=3
        )
        current.bind_conversation("h1", [])
        await current.observe_turn("謝謝你昨天陪我", "不用謝。")
        while worker.calls == 0:
            await asyncio.sleep(0)
        await current.observe_turn("對了", "嗯？")
        gate.set()
        await current.settle()
        snapshot = current.snapshot()
        await current.close()
        return snapshot

    snapshot = run(scenario())
    assert snapshot.favorability == pytest.approx(50.0)
    assert snapshot.emotion == "calm"


def test_a_result_that_arrives_too_late_is_dropped(tmp_path):
    async def scenario():
        gate = asyncio.Event()
        worker = Worker(warm_only_when_thanked, gate=gate)
        current = session(
            tmp_path, {"emotion": worker}, emotion_every=4, max_rebase_turns=1
        )
        current.bind_conversation("h1", [])
        for text in ("一", "二", "三"):
            await current.observe_turn(text, "嗯。")
        await current.observe_turn("謝謝你昨天陪我", "不用謝。")
        while worker.calls == 0:
            await asyncio.sleep(0)
        await current.observe_turn("五", "嗯。")
        await current.observe_turn("六", "嗯。")
        gate.set()
        await current.settle()
        snapshot = current.snapshot()
        await current.close()
        return snapshot

    snapshot = run(scenario())
    assert snapshot.favorability == pytest.approx(50.0)
    assert snapshot.emotion == "neutral"


def test_an_older_job_is_abandoned_when_a_newer_one_of_its_kind_arrives(tmp_path):
    """使用者講得比背景快的時候，舊的那一筆跑完也只會讓路給新的，白白佔用模型。
    不管它在排隊還是已經在跑，都直接放棄。"""

    async def scenario():
        gate = asyncio.Event()
        worker = Worker(warm_only_when_thanked, gate=gate)
        current = session(tmp_path, {"emotion": worker}, emotion_every=1)
        await current.observe_turn("謝謝你昨天陪我", "不用謝。", history_uid="h1")
        while worker.calls == 0:
            await asyncio.sleep(0)
        await current.observe_turn("對了", "嗯？", history_uid="h1")
        await current.observe_turn("還有一件事", "說吧。", history_uid="h1")
        gate.set()
        await current.settle()
        snapshot = current.snapshot()
        await current.close()
        return worker.abandoned, snapshot

    abandoned, snapshot = run(scenario())
    assert abandoned >= 1
    assert snapshot.favorability == pytest.approx(50.0)
    assert snapshot.emotion == "calm"


def test_her_mood_never_waits_for_other_background_work(tmp_path):
    """實測：她講完的那一刻，上一輪被打斷的記憶工作先拿到模型；這一輪的情緒分析
    排在它後面，等到輪到時又碰上下一輪對話。8 輪只提交了 3 次。情緒決定下一句的
    心情，所以它有自己的通道。"""

    async def scenario():
        gate = asyncio.Event()
        workers = {
            "memory": Worker(
                {"items": [], "confidence": 0.5, "evidence": []},
                gate=gate,
                name="memory",
            ),
            "emotion": Worker(WARM, name="emotion"),
        }
        current = session(tmp_path, workers, emotion_every=2, memory_every=1)
        await current.observe_turn("第一輪", "嗯。", history_uid="h1")
        while workers["memory"].calls == 0:
            await asyncio.sleep(0)
        await current.observe_turn("謝謝你昨天陪我", "不用謝。", history_uid="h1")
        for _ in range(200):
            await asyncio.sleep(0)
            if current.snapshot().emotion == "happy":
                break
        while_memory_is_still_running = current.snapshot().emotion
        gate.set()
        await current.settle()
        await current.close()
        return while_memory_is_still_running

    assert run(scenario()) == "happy"


def test_the_other_background_jobs_use_the_model_one_at_a_time(tmp_path):
    async def scenario():
        workers = {
            "memory": Worker(
                {"items": [], "confidence": 0.5, "evidence": []}, name="memory"
            ),
            "goal": Worker({"goals": [], "confidence": 0, "evidence": []}, name="goal"),
            "reflection": Worker(
                {
                    "insight": "i",
                    "belief_candidate": None,
                    "confidence": 0.9,
                    "evidence": [],
                },
                name="reflection",
            ),
        }
        current = session(
            tmp_path, workers, memory_every=1, goal_every=1, reflection_every=1
        )
        current.foreground_started()
        await current.observe_turn("上一輪", "嗯。", history_uid="h1")
        for _ in range(20):
            await asyncio.sleep(0)
        current.foreground_finished()
        await current.settle()
        await current.close()
        return list(Worker.order), Worker.most_at_once

    order, most_at_once = run(scenario())
    assert order == ["memory", "goal", "reflection"]
    assert most_at_once == 1


def test_a_job_she_interrupted_once_is_left_to_finish_the_next_time(tmp_path):
    """目標和反思一次要 10 到 20 秒，比兩輪對話之間的空檔還長。每次都打斷重來的話
    它們永遠跑不完，運算全部白費。"""

    async def scenario():
        gate = asyncio.Event()
        worker = Worker({"items": [], "confidence": 0.5, "evidence": []}, gate=gate)
        current = session(tmp_path, {"memory": worker}, memory_every=1)
        await current.observe_turn("你好", "嗯。", history_uid="h1")
        while worker.calls == 0:
            await asyncio.sleep(0)
        current.foreground_started()
        for _ in range(20):
            await asyncio.sleep(0)
        after_first = worker.abandoned
        current.foreground_finished()
        while worker.calls < 2:
            await asyncio.sleep(0)
        current.foreground_started()
        for _ in range(20):
            await asyncio.sleep(0)
        after_second = worker.abandoned
        current.foreground_finished()
        gate.set()
        await current.settle()
        await current.close()
        return after_first, after_second, worker.calls

    assert run(scenario()) == (1, 1, 2)


def test_memory_jobs_are_never_dropped_because_each_turn_has_its_own_facts(tmp_path):
    async def scenario():
        gate = asyncio.Event()
        worker = Worker({"items": [], "confidence": 0.5, "evidence": []}, gate=gate)
        current = session(tmp_path, {"memory": worker}, memory_every=1)
        current.bind_conversation("h1", [])
        await current.observe_turn("一", "嗯。")
        while worker.calls == 0:
            await asyncio.sleep(0)
        await current.observe_turn("二", "嗯。")
        await current.observe_turn("三", "嗯。")
        gate.set()
        await current.settle()
        await current.close()
        return worker.calls

    assert run(scenario()) == 3


def goal_citing_the_event(messages):
    event_id = re.search(r'"event": \{.*?"id": "([^"]+)"', messages[1].content).group(1)
    return {
        "goals": [
            {
                "objective": "把畫完成給用戶看",
                "horizon": "short_term",
                "urgency": 0.8,
                "conflict_key": None,
                "motivation_signals": [
                    {
                        "kind": "explicit_request",
                        "strength": 0.9,
                        "source_type": "event",
                        "source_id": event_id,
                        "rationale": "對方開口要看",
                    }
                ],
                "confidence": 0.9,
            }
        ],
        "confidence": 0.9,
        "evidence": [],
    }


def test_goals_and_thoughts_reach_the_snapshot(tmp_path):
    async def scenario():
        workers = {
            "goal": Worker(goal_citing_the_event),
            "reflection": Worker(
                {
                    "insight": "對方很期待那幅畫",
                    "belief_candidate": None,
                    "confidence": 0.9,
                    "evidence": [],
                }
            ),
        }
        current = session(tmp_path, workers, goal_every=1, reflection_every=1)
        current.bind_conversation("h1", [])
        await current.observe_turn("畫好了就給我看", "知道了啦。")
        await current.settle()
        await current.close()
        return session(tmp_path, {}).snapshot()

    snapshot = run(scenario())
    assert list(snapshot.goals) == ["把畫完成給用戶看"]
    assert list(snapshot.thoughts) == ["對方很期待那幅畫"]


def test_a_worker_that_is_down_never_reaches_the_conversation(tmp_path):
    async def scenario():
        current = session(
            tmp_path, {"emotion": Worker(WARM, fail=True)}, emotion_every=1
        )
        current.bind_conversation("h1", [])
        await current.observe_turn("謝謝你", "嗯。")
        await current.settle()
        snapshot = current.snapshot()
        await current.close()
        return snapshot

    snapshot = run(scenario())
    assert snapshot.emotion == "neutral"
    assert snapshot.trust == pytest.approx(50.3)


def test_a_role_without_a_model_is_skipped_instead_of_failing(tmp_path):
    async def scenario():
        current = session(tmp_path, {}, emotion_every=1)
        current.bind_conversation("h1", [])
        await current.observe_turn("謝謝你", "嗯。")
        await current.settle()
        await current.close()
        return current.snapshot()

    assert run(scenario()).trust == pytest.approx(50.3)


def test_workers_run_on_their_own_cadence(tmp_path):
    async def scenario():
        summary = Worker({"summary": "聊了天氣", "confidence": 0.9, "evidence": []})
        current = session(tmp_path, {"summary": summary}, summary_every=3)
        current.bind_conversation("h1", [])
        for index in range(3):
            await current.observe_turn(f"第 {index} 句", "嗯。")
            await current.settle()
        await current.close()
        return summary.calls

    assert run(scenario()) == 1


def test_engine_memory_belongs_to_the_conversation_it_came_from(tmp_path):
    def fact(messages):
        return {
            "items": [
                {
                    "summary": "對方養了一隻貓叫饅頭",
                    "kind": "fact",
                    "importance": 0.8,
                    "confidence": 0.9,
                    "evidence": "我養了一隻貓叫饅頭",
                }
            ],
            "confidence": 0.9,
            "evidence": [],
        }

    async def scenario():
        current = session(tmp_path, {"memory": Worker(fact)}, memory_every=1)
        current.bind_conversation("h1", [])
        await current.observe_turn("我養了一隻貓叫饅頭", "饅頭？")
        await current.settle()
        in_first = current.memories()
        current.bind_conversation("h2", [])
        in_second = current.memories()
        await current.close()
        return in_first, in_second

    in_first, in_second = run(scenario())
    assert "對方養了一隻貓叫饅頭" in in_first
    assert in_second == []


def test_binding_a_conversation_gives_the_workers_its_recent_lines(tmp_path):
    seen = {}

    def capture(messages):
        seen["prompt"] = messages[1].content
        return {"summary": "s", "confidence": 0.9, "evidence": []}

    async def scenario():
        current = session(tmp_path, {"summary": Worker(capture)}, summary_every=1)
        current.bind_conversation(
            "h1",
            [
                ("assistant", "沒頭沒尾的一句"),
                ("user", "昨天說到哪"),
                ("assistant", "說到時間機器"),
            ],
        )
        await current.observe_turn("繼續吧", "好。")
        await current.settle()
        await current.close()

    run(scenario())
    assert "說到時間機器" in seen["prompt"]
    assert "沒頭沒尾的一句" not in seen["prompt"]


def test_a_blank_turn_is_not_recorded(tmp_path):
    async def scenario():
        current = session(tmp_path, {})
        current.bind_conversation("h1", [])
        await current.observe_turn("   ", "嗯。")
        await current.observe_turn("你好", "")
        await current.close()
        return current.snapshot()

    assert run(scenario()).trust == pytest.approx(50.0)


def test_flushing_saves_her_state_without_stopping_the_session(tmp_path):
    async def scenario():
        current = session(tmp_path, {})
        current.bind_conversation("h1", [])
        await current.observe_turn("你好", "嗯。")
        (tmp_path / "engine" / "state.json").unlink()
        current.flush()
        saved = (tmp_path / "engine" / "state.json").is_file()
        await current.observe_turn("還在嗎", "在。")
        snapshot = current.snapshot()
        await current.close()
        return saved, snapshot

    saved, snapshot = run(scenario())
    assert saved is True
    assert snapshot.trust == pytest.approx(50.6)


def test_background_work_waits_while_she_is_talking(tmp_path):
    """實測：背景工作跟對話搶同一顆模型，第一句的延遲中位數從 2.6 秒變成 4.7 秒。
    她在生成回覆的時候，背景工作不可以開始新的呼叫。"""

    async def scenario():
        worker = Worker(NEUTRAL)
        current = session(tmp_path, {"emotion": worker}, emotion_every=1)
        current.bind_conversation("h1", [])
        current.foreground_started()
        await current.observe_turn("上一輪", "嗯。")
        for _ in range(20):
            await asyncio.sleep(0)
        while_talking = worker.calls
        current.foreground_finished()
        await current.settle()
        await current.close()
        return while_talking, worker.calls

    assert run(scenario()) == (0, 1)


def test_a_call_already_running_is_abandoned_when_she_starts_talking_and_redone_after(
    tmp_path,
):
    async def scenario():
        gate = asyncio.Event()
        worker = Worker(WARM, gate=gate)
        current = session(tmp_path, {"emotion": worker}, emotion_every=1)
        current.bind_conversation("h1", [])
        await current.observe_turn("謝謝你昨天陪我", "不用謝。")
        while worker.calls == 0:
            await asyncio.sleep(0)
        current.foreground_started()
        for _ in range(20):
            await asyncio.sleep(0)
        gate.set()
        calls_while_talking = worker.calls
        current.foreground_finished()
        await current.settle()
        snapshot = current.snapshot()
        await current.close()
        return calls_while_talking, worker.calls, snapshot

    while_talking, total, snapshot = run(scenario())
    assert (while_talking, total) == (1, 2)
    assert snapshot.favorability == pytest.approx(54.0)


def test_overlapping_conversations_all_have_to_finish_before_work_resumes(tmp_path):
    async def scenario():
        worker = Worker(NEUTRAL)
        current = session(tmp_path, {"emotion": worker}, emotion_every=1)
        current.bind_conversation("h1", [])
        current.foreground_started()
        current.foreground_started()
        await current.observe_turn("上一輪", "嗯。")
        current.foreground_finished()
        for _ in range(20):
            await asyncio.sleep(0)
        still_waiting = worker.calls
        current.foreground_finished()
        current.foreground_finished()  # 多呼叫一次不可以變成負的
        await current.settle()
        await current.close()
        return still_waiting, worker.calls

    assert run(scenario()) == (0, 1)


def test_a_conversation_that_never_reports_finishing_cannot_freeze_her_forever(
    tmp_path,
):
    async def scenario():
        worker = Worker(NEUTRAL)
        current = session(
            tmp_path,
            {"emotion": worker},
            emotion_every=1,
            foreground_patience_seconds=0.05,
        )
        current.bind_conversation("h1", [])
        current.foreground_started()
        await current.observe_turn("上一輪", "嗯。")
        await current.settle()
        await current.close()
        return worker.calls

    assert run(scenario()) == 1


def cat_fact_when_quoted(messages):
    """只有使用者這一輪真的講了貓，才交得出這筆記憶。"""
    if (
        "我養了一隻貓叫饅頭"
        not in messages[1].content.split("User lines to extract from:")[1]
    ):
        return {"items": [], "confidence": 0.5, "evidence": []}
    return {
        "items": [
            {
                "summary": "對方養了一隻貓叫饅頭",
                "kind": "fact",
                "importance": 0.8,
                "confidence": 0.9,
                "evidence": "我養了一隻貓叫饅頭",
            }
        ],
        "confidence": 0.9,
        "evidence": [],
    }


def test_a_late_memory_lands_in_the_conversation_it_came_from(tmp_path):
    """引擎提交記憶時用的是「提交當下」的對話範圍。背景結果晚到、而使用者已經切到
    另一段對話的話，記憶會落在新的那一段——私事就這樣跨了對話。"""

    async def scenario():
        gate = asyncio.Event()
        worker = Worker(cat_fact_when_quoted, gate=gate)
        current = session(tmp_path, {"memory": worker}, memory_every=1)
        await current.observe_turn("我養了一隻貓叫饅頭", "饅頭？", history_uid="h1")
        while worker.calls == 0:
            await asyncio.sleep(0)
        await current.observe_turn("你好", "嗯。", history_uid="h2")
        gate.set()
        await current.settle()
        found = current.memories("h1"), current.memories("h2")
        await current.close()
        return found

    in_first, in_second = run(scenario())
    assert in_first == ["對方養了一隻貓叫饅頭"]
    assert in_second == []


def test_two_conversations_taking_turns_each_keep_their_own_recent_lines(tmp_path):
    prompts = []

    def capture(messages):
        prompts.append(messages[1].content)
        return {"summary": "s", "confidence": 0.9, "evidence": []}

    async def scenario():
        current = session(tmp_path, {"summary": Worker(capture)}, summary_every=1)
        for history_uid, text in (("h1", "甲一"), ("h2", "乙一"), ("h1", "甲二")):
            await current.observe_turn(text, "嗯。", history_uid=history_uid)
            await current.settle()
        await current.close()

    run(scenario())
    assert "甲一" in prompts[2]
    assert "乙一" not in prompts[2]


def test_a_conversation_is_seeded_once_and_then_keeps_what_it_has_seen(tmp_path):
    prompts = []

    def capture(messages):
        prompts.append(messages[1].content)
        return {"summary": "s", "confidence": 0.9, "evidence": []}

    async def scenario():
        current = session(tmp_path, {"summary": Worker(capture)}, summary_every=1)
        current.bind_conversation("h1", [("user", "載入的舊話"), ("assistant", "嗯。")])
        await current.observe_turn("新的一句", "好。", history_uid="h1")
        await current.settle()
        current.bind_conversation("h1", [])
        await current.observe_turn("再一句", "好。", history_uid="h1")
        await current.settle()
        await current.close()

    run(scenario())
    assert "載入的舊話" in prompts[0]
    assert "新的一句" in prompts[1]


def test_she_frees_the_model_herself_when_nobody_reports_the_reply_ended(tmp_path):
    """審查抓到的：等她講完的時間算在背景工作的逾時裡，而預設逾時（60 秒）比耐心
    （120 秒）短，所以工作永遠先逾時、耐心永遠不會觸發，背景認知就此停住。"""

    async def scenario():
        worker = Worker(NEUTRAL)
        current = session(
            tmp_path,
            {"emotion": worker},
            emotion_every=1,
            timeout_seconds=0.1,
            foreground_patience_seconds=0.3,
        )
        current.foreground_started()
        await current.observe_turn("上一輪", "嗯。", history_uid="h1")
        await current.settle()
        first = worker.calls
        await current.observe_turn("下一輪", "嗯。", history_uid="h1")
        await current.settle()
        await current.close()
        return first, worker.calls

    assert run(scenario()) == (1, 2)


def test_a_model_call_that_never_returns_is_given_up_on(tmp_path):
    async def scenario():
        worker = Worker(NEUTRAL, gate=asyncio.Event())
        current = session(
            tmp_path, {"emotion": worker}, emotion_every=1, timeout_seconds=0.05
        )
        await current.observe_turn("你好", "嗯。", history_uid="h1")
        await asyncio.wait_for(current.settle(), 2)
        snapshot = current.snapshot()
        await current.close()
        return snapshot

    assert run(scenario()).emotion == "neutral"


def test_a_retired_session_stops_writing_so_its_successor_is_not_overwritten(tmp_path):
    """每次儲存設定都會重建 agent。舊的工作階段還被別的連線拿著，它之後的存檔會
    把新的那一個累積的狀態蓋掉。"""

    async def scenario():
        old = session(tmp_path, {})
        await old.observe_turn("一", "嗯。", history_uid="h1")
        old.retire()
        new = session(tmp_path, {})
        for text in ("二", "三", "四"):
            await new.observe_turn(text, "嗯。", history_uid="h1")
        await old.observe_turn("舊連線又講了一句", "嗯。", history_uid="h1")
        old.flush()
        await new.close()
        return session(tmp_path, {}).snapshot()

    assert run(scenario()).trust == pytest.approx(50.0 + 0.3 * 4)


def test_a_job_cancelled_while_waiting_for_the_model_ends_as_cancelled():
    """等著用模型的工作被取消時，曾經丟出 ValueError（它已經不在等候名單裡了）。
    引擎把那當成一般的失敗，工作位的取消就這樣被吃掉，關機時整個行程卡住。"""
    from src.open_llm_vtuber.character_engine.session import _ModelAccess

    async def scenario():
        access = _ModelAccess(patience_seconds=60)
        release = asyncio.Event()

        async def slow():
            await release.wait()
            return "first"

        async def quick():
            return "later"

        first = asyncio.ensure_future(access.call(0, slow, 5))
        await asyncio.sleep(0)
        waiting = asyncio.ensure_future(access.call(1, quick, 5))
        behind = asyncio.ensure_future(access.call(2, quick, 5))
        await asyncio.sleep(0)
        waiting.cancel()
        # 同一瞬間剛好有別的工作用完模型：它會把已經取消的那一個從名單上拿掉。
        access._pass_on()
        release.set()
        return await asyncio.gather(first, waiting, behind, return_exceptions=True)

    first, waiting, behind = asyncio.run(scenario())
    assert first == "first"
    assert isinstance(waiting, asyncio.CancelledError)
    assert behind == "later"
