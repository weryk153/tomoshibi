"""表情與動作交給背景模型挑（character_config.expression_source: background）。

主模型不再在台詞裡帶 [joy] 標籤；每一句送 TTS 的同時問背景模型這句該配什麼
表情、動作。逾時（2.5 秒）或答不出來就是沒有，聲音照播。預設 tags，一切照舊。
"""

import asyncio
import json
import time
from types import SimpleNamespace

from src.open_llm_vtuber import expression_pick
from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.avatar_model import AvatarModel
from src.open_llm_vtuber.expression_pick import (
    ExpressionPicker,
    apply_pick,
    pick_actions,
    picker_for,
)

EXPRESSIONS = ["neutral", "joy", "sadness", "anger", "surprise"]
MOTIONS = ["nod", "wave", "special_1"]


# ---------------------------------------------------------------- pick_actions


def test_a_clean_answer_is_taken_as_is():
    raw = '{"expression": "joy", "motion": "wave", "intensity": 0.7}'

    assert pick_actions("你好！", EXPRESSIONS, MOTIONS, raw) == {
        "expression": "joy",
        "motion": "wave",
        "intensity": 0.7,
    }


def test_anything_not_on_the_lists_is_dropped():
    raw = '{"expression": "smug", "motion": "backflip", "intensity": 0.5}'

    assert pick_actions("哼。", EXPRESSIONS, MOTIONS, raw) == {
        "expression": None,
        "motion": None,
        "intensity": 0.5,
    }


def test_tag_spelling_and_case_are_forgiven():
    raw = '{"expression": "[Joy]", "motion": " NOD ", "intensity": 1}'

    picked = pick_actions("嗯！", EXPRESSIONS, MOTIONS, raw)

    assert (picked["expression"], picked["motion"]) == ("joy", "nod")


def test_null_in_words_is_null():
    raw = '{"expression": "null", "motion": "none", "intensity": 0.3}'

    picked = pick_actions("嗯。", EXPRESSIONS, MOTIONS, raw)

    assert (picked["expression"], picked["motion"]) == (None, None)


def test_intensity_is_kept_between_zero_and_one():
    def intensity(value):
        raw = json.dumps({"expression": "joy", "motion": None, "intensity": value})
        return pick_actions("好耶！", EXPRESSIONS, MOTIONS, raw)["intensity"]

    assert intensity(1.8) == 1.0
    assert intensity(-0.4) == 0.0
    assert intensity("very") == 1.0
    assert intensity(None) == 1.0


def test_a_fenced_answer_with_its_thinking_and_a_repeat_is_read():
    raw = (
        "<think>她在開心。</think>\n```json\n"
        '{"expression": "joy", "motion": null, "intensity": 0.6}\n```\n'
        '{"expression": "joy", "motion": null, "intensity": 0.6}'
    )

    assert pick_actions("好耶！", EXPRESSIONS, MOTIONS, raw)["expression"] == "joy"


def test_an_answer_that_is_not_json_gives_nothing():
    assert pick_actions("好耶！", EXPRESSIONS, MOTIONS, "joy, wave") is None
    assert pick_actions("好耶！", EXPRESSIONS, MOTIONS, '["joy"]') is None
    assert pick_actions("好耶！", EXPRESSIONS, MOTIONS, "") is None


def test_a_blank_line_gets_nothing():
    raw = '{"expression": "joy", "motion": "wave", "intensity": 1}'

    assert pick_actions("  ", EXPRESSIONS, MOTIONS, raw) is None


# ---------------------------------------------------------------- 問模型


class _Client:
    def __init__(self, answer='{"expression": "joy", "motion": null}', delay=0.0):
        self.answer = answer
        self.delay = delay
        self.asked: list[list[dict]] = []

    async def complete(self, messages):
        self.asked.append(messages)
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def _picker(client, *, mood=None, timeout=2.5):
    return ExpressionPicker(
        client=client,
        expressions=EXPRESSIONS,
        motions={"nod": "點頭", "wave": "揮手", "special_1": ""},
        mood=lambda: mood,
        timeout_seconds=timeout,
    )


def test_the_model_reads_the_line_the_one_before_her_mood_and_the_lists():
    client = _Client()
    picker = _picker(client, mood={"mood": "sadness", "intensity": 0.4})

    asyncio.run(picker.ask("今天好累。", previous="你來啦。"))

    prompt = "\n".join(m["content"] for m in client.asked[0])
    for expected in ("今天好累。", "你來啦。", "sadness", "joy", "wave", "揮手"):
        assert expected in prompt


def test_the_pick_comes_back_filtered():
    picked = asyncio.run(_picker(_Client()).ask("好耶！", previous=""))

    assert picked == {"expression": "joy", "motion": None, "intensity": 1.0}


def test_a_slow_model_is_given_up_on_without_holding_the_voice():
    picker = _picker(_Client(delay=5.0), timeout=0.05)

    started = time.monotonic()
    picked = asyncio.run(picker.ask("好耶！", previous=""))

    assert picked is None
    assert time.monotonic() - started < 1.0


def test_a_failing_model_gives_nothing():
    picker = _picker(_Client(answer=RuntimeError("connection refused")))

    assert asyncio.run(picker.ask("好耶！", previous="")) is None


def test_a_mood_that_cannot_be_read_is_left_out():
    client = _Client()

    def broken():
        raise RuntimeError("engine gone")

    picker = ExpressionPicker(
        client=client, expressions=EXPRESSIONS, motions={}, mood=broken
    )
    assert asyncio.run(picker.ask("好耶！", previous="")) is not None


# ---------------------------------------------------------------- 誰有挑選器


def _character(source, *, background=True):
    engine = SimpleNamespace(
        background_base_url="http://127.0.0.1:1235/v1" if background else "",
        background_model="qwen/qwen3.5-9b" if background else "",
        background_api_key="",
    )
    return SimpleNamespace(
        expression_source=source,
        agent_config=SimpleNamespace(
            agent_settings=SimpleNamespace(
                character_engine_agent=engine,
                conversation=SimpleNamespace(llm_provider="lmstudio_llm"),
            ),
            llm_configs=SimpleNamespace(
                lmstudio_llm=SimpleNamespace(extra_body={}, llm_api_key="")
            ),
        ),
    )


def _model(emotions=None, motions=None):
    model = AvatarModel.__new__(AvatarModel)
    model.emo_map = emotions or {"neutral": 0, "joy": 3, "sadness": 1}
    model.motion_map = (
        motions
        if motions is not None
        else {
            "nod": {"group": "", "index": 1, "label": "點頭"},
            "wave": {"group": "", "index": 2},
        }
    )
    model.model_info = {}
    return model


def test_tags_mode_has_no_picker():
    assert picker_for(_character("tags"), _model(), agent=None) is None


def test_a_character_without_the_setting_has_no_picker():
    character = _character("background")
    del character.expression_source

    assert picker_for(character, _model(), agent=None) is None


def test_background_mode_without_a_background_model_stays_on_tags():
    assert (
        picker_for(_character("background", background=False), _model(), None) is None
    )


def test_a_model_with_nothing_to_choose_from_has_no_picker():
    assert (
        picker_for(_character("background"), _model({"neutral": 0}, {}), None) is None
    )
    assert picker_for(_character("background"), None, None) is None


def test_background_mode_picks_from_the_models_own_lists():
    agent = SimpleNamespace(mood_message=lambda: {"mood": "joy", "intensity": 0.5})

    picker = picker_for(_character("background"), _model(), agent)

    assert picker.expressions == ["neutral", "joy", "sadness"]
    assert picker.motions == {"nod": "點頭", "wave": ""}
    assert picker.mood() == {"mood": "joy", "intensity": 0.5}


def test_uses_background_expressions_follows_the_same_rule():
    assert expression_pick.uses_background_expressions(_character("background"))
    assert not expression_pick.uses_background_expressions(_character("tags"))
    assert not expression_pick.uses_background_expressions(
        _character("background", background=False)
    )


# ---------------------------------------------------------------- 放進 actions


def test_the_pick_becomes_the_payloads_expression_and_motion():
    actions = apply_pick(
        Actions(), {"expression": "joy", "motion": "nod", "intensity": 0.6}, _model()
    )

    assert actions.expressions == [3]
    assert actions.expression_intensities == [0.6]
    assert actions.motions == [{"group": "", "index": 1}]


def test_a_tag_she_wrote_anyway_wins():
    written = Actions(expressions=[1], expression_intensities=[1.0])

    actions = apply_pick(
        written, {"expression": "joy", "motion": None, "intensity": 0.6}, _model()
    )

    assert actions.expressions == [1]
    assert actions.motions is None


def test_no_pick_leaves_the_actions_alone():
    actions = Actions(emotion="joy")

    assert apply_pick(actions, None, _model()) is actions
    assert apply_pick(None, None, _model()) is None
    assert apply_pick(
        None, {"expression": "joy", "motion": None, "intensity": 1.0}, _model()
    ).expressions == [3]


# ---------------------------------------------------------------- 合成管線

from src.open_llm_vtuber.conversations import tts_manager as tts_manager_module  # noqa: E402
from src.open_llm_vtuber.conversations.conversation_utils import (  # noqa: E402
    handle_sentence_output,
)
from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager  # noqa: E402
from src.open_llm_vtuber.tts.tts_interface import TTSInterface  # noqa: E402
from src.open_llm_vtuber.utils.stream_audio import prepare_audio_payload  # noqa: E402


class _Engine(TTSInterface):
    def __init__(self, delay=0.0):
        self.delay = delay

    def generate_audio(self, text, file_name_no_ext=None):  # pragma: no cover
        raise NotImplementedError

    async def async_generate_audio(self, text, file_name_no_ext=None):
        if self.delay:
            await asyncio.sleep(self.delay)
        return f"{text}.wav"

    def remove_file(self, filepath, verbose=True):
        pass


def _fake_prepare_audio_payload(audio_path, **kwargs):
    kwargs["audio_path"] = None
    payload = prepare_audio_payload(**kwargs)
    payload["audio"] = f"AUDIO:{audio_path}" if audio_path else None
    return payload


class _Send:
    def __init__(self):
        self.messages: list[dict] = []

    async def __call__(self, data):
        self.messages.append(json.loads(data))


class _Sentences:
    def __init__(self, lines):
        self.lines = lines

    async def __aiter__(self):
        for display, tts in self.lines:
            yield DisplayText(text=display), tts, Actions()


def _run(monkeypatch, lines, picker, engine=None):
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )

    async def go():
        manager = TTSTaskManager()
        send = _Send()
        await handle_sentence_output(
            _Sentences(lines),
            live2d_model=_model(),
            tts_engine=engine or _Engine(),
            websocket_send=send,
            tts_manager=manager,
            expression_picker=picker,
        )
        await asyncio.gather(*manager.task_list)
        await manager._payload_queue.join()
        return send.messages

    return asyncio.run(go())


def test_each_line_gets_its_pick_in_its_own_payload(monkeypatch):
    class _ByLine(_Client):
        async def complete(self, messages):
            self.asked.append(messages)
            line = messages[-1]["content"]
            if "好累" in line.split("Line:")[-1]:
                return '{"expression": "sadness", "motion": null, "intensity": 0.5}'
            return '{"expression": "joy", "motion": "nod", "intensity": 1}'

    client = _ByLine()
    messages = _run(
        monkeypatch,
        [("你來啦！", "你來啦！"), ("今天好累。", "今天好累。")],
        _picker(client),
    )

    assert [m["actions"]["expressions"] for m in messages] == [[3], [1]]
    assert messages[0]["actions"]["motions"] == [{"group": "", "index": 1}]
    assert "motions" not in messages[1]["actions"]
    assert [m["audio"] for m in messages] == [
        "AUDIO:你來啦！.wav",
        "AUDIO:今天好累。.wav",
    ]
    # 第二句問的時候，前一句是第一句。
    assert "你來啦！" in client.asked[1][-1]["content"]


def test_a_pick_that_times_out_leaves_the_voice_playing(monkeypatch):
    messages = _run(
        monkeypatch,
        [("你來啦！", "你來啦！")],
        _picker(_Client(delay=5.0), timeout=0.05),
    )

    (message,) = messages
    assert message["audio"] == "AUDIO:你來啦！.wav"
    assert "expressions" not in (message["actions"] or {})


def test_the_pick_runs_while_the_voice_is_made(monkeypatch):
    """合成 0.3 秒、挑選 0.3 秒：並行的話一句大約 0.3 秒，不是 0.6。"""
    started = time.monotonic()
    _run(
        monkeypatch,
        [("你來啦！", "你來啦！")],
        _picker(_Client(delay=0.3)),
        engine=_Engine(delay=0.3),
    )

    assert time.monotonic() - started < 0.55


def test_a_silent_line_gets_a_pick_too(monkeypatch):
    (message,) = _run(monkeypatch, [("*歪頭*", "")], _picker(_Client()))

    assert message["audio"] is None
    assert message["actions"]["expressions"] == [3]


def test_tags_mode_sends_what_it_always_sent(monkeypatch):
    """沒有挑選器（tags 模式）：payload 跟沒有這個功能時一字不差。"""
    off = _run(monkeypatch, [("你來啦！", "你來啦！"), ("*歪頭*", "")], None)

    expected = []
    for display, tts in (("你來啦！", "你來啦！"), ("*歪頭*", "")):
        payload = _fake_prepare_audio_payload(
            f"{tts}.wav" if tts else None,
            display_text=DisplayText(text=display),
            actions=Actions(),
            subtitle_text=display,
        )
        payload["keep_subtitle"] = False
        expected.append(payload)
    assert json.dumps(off) == json.dumps(expected)


# ---------------------------------------------------------------- 不擋聲音、一次一個、語氣


class _Voiced(TTSInterface):
    """記下每句拿到的語氣（emotion_refs 用的那個關鍵字）。"""

    supports_emotion = True

    def __init__(self, delay=0.0):
        self.delay = delay
        self.emotions: list = []

    def generate_audio(self, text, file_name_no_ext=None, emotion=None):
        if self.delay:
            time.sleep(self.delay)
        self.emotions.append(emotion)
        return f"{text}.wav"

    def remove_file(self, filepath, verbose=True):
        pass


class _Paced(_Sentences):
    """一句一句慢慢來，像主模型邊想邊說。"""

    def __init__(self, lines, gap):
        super().__init__(lines)
        self.gap = gap

    async def __aiter__(self):
        for index, (display, tts) in enumerate(self.lines):
            if index:
                await asyncio.sleep(self.gap)
            yield DisplayText(text=display), tts, Actions()


def test_a_slow_pick_holds_the_voice_only_a_moment(monkeypatch):
    """合成好了、挑選還沒好：最多再等 GRACE_SECONDS，聲音就先走。"""
    from src.open_llm_vtuber import expression_pick

    started = time.monotonic()
    (message,) = _run(
        monkeypatch,
        [("你來啦！", "你來啦！")],
        _picker(_Client(delay=3.0), timeout=6.0),
        engine=_Engine(delay=0.1),
    )
    assert time.monotonic() - started < 0.1 + expression_pick.GRACE_SECONDS + 0.3
    assert message["audio"] == "AUDIO:你來啦！.wav"
    assert "expressions" not in (message["actions"] or {})


def test_a_silent_line_waits_only_a_moment_for_its_pick(monkeypatch):
    from src.open_llm_vtuber import expression_pick

    started = time.monotonic()
    (message,) = _run(
        monkeypatch, [("*歪頭*", "")], _picker(_Client(delay=3.0), timeout=6.0)
    )
    assert time.monotonic() - started < expression_pick.SILENT_GRACE_SECONDS + 0.3
    assert "expressions" not in (message["actions"] or {})


def test_one_pick_at_a_time():
    """背景模型同時只問一句：忙著的時候這句不挑，不在它那裡排隊。"""
    client = _Client(delay=0.3)
    picker = _picker(client, timeout=6.0)

    async def both():
        return await asyncio.gather(picker.ask("你來啦！"), picker.ask("今天好累。"))

    first, second = asyncio.run(both())
    assert first is not None and second is None
    assert len(client.asked) == 1


def test_the_voice_takes_her_mood_before_anything_is_picked(monkeypatch):
    engine = _Voiced()
    picker = _picker(
        _Client(delay=3.0), mood={"mood": "sadness", "intensity": 0.8}, timeout=6.0
    )
    _run(monkeypatch, [("今天好累。", "今天好累。")], picker, engine=engine)
    assert engine.emotions == ["sadness"]


def test_the_first_pick_sets_the_voice_for_the_rest_of_the_reply(monkeypatch):
    """跟標籤一樣：這則回覆第一個挑到的表情，就是後面幾句的語氣。"""
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )
    engine = _Voiced(delay=0.2)
    picker = _picker(
        _Client(delay=0.05), mood={"mood": "sadness", "intensity": 0.8}, timeout=6.0
    )

    async def go():
        manager = TTSTaskManager()
        await handle_sentence_output(
            _Paced([("你來啦！", "你來啦！"), ("好開心！", "好開心！")], gap=0.3),
            live2d_model=_model(),
            tts_engine=engine,
            websocket_send=_Send(),
            tts_manager=manager,
            expression_picker=picker,
        )
        await asyncio.gather(*manager.task_list)
        await manager._payload_queue.join()

    asyncio.run(go())
    assert engine.emotions == ["sadness", "joy"]
