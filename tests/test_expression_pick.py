"""表情與動作交給引擎挑（character_config.expression_source: background）。

主模型不再在台詞裡帶 [joy] 標籤；每一句送 TTS 的同時請引擎（reply_actions）挑這句
該配什麼表情、動作。挑選本身（提示、讀答案、一次一句、語氣）的測試在引擎；這裡測
Tomoshibi 這一側：清單與心情對照、誰有挑選器、放進 actions、聲音不等它。
預設 tags，一切照舊。
"""

import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber import expression_pick
from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.avatar_model import AvatarModel
from src.open_llm_vtuber.expression_pick import (
    EnginePicker,
    apply_pick,
    avatar_choices,
    mood_faces,
    picker_for,
)

try:
    from ai_character_engine.companion import AvatarChoices  # noqa: F401

    ENGINE_PICKS = True
except ImportError:  # 引擎 1.3.0 以前
    ENGINE_PICKS = False
needs_engine = pytest.mark.skipif(
    not ENGINE_PICKS, reason="ai-character-engine 1.3.0 or later"
)


class _Actions:
    """引擎的 ReplyActions 的替身：記下問了哪幾句，晚一點或答 None。"""

    def __init__(
        self, answer=("joy", None, 1.0), *, delay=0.0, mood_face=None, can_pick=True
    ):
        self.answer = answer
        self.delay = delay
        self.mood_face = mood_face
        self.can_pick = can_pick
        self.lines: list[str] = []
        self.first = None

    async def pick(self, line):
        self.lines.append(line)
        if self.delay:
            await asyncio.sleep(self.delay)
        answer = self.answer(line) if callable(self.answer) else self.answer
        if answer is None:
            return None
        expression, motion, intensity = answer
        if expression and self.first is None:
            self.first = expression
        return SimpleNamespace(
            expression=expression, motion=motion, intensity=intensity
        )

    def voice(self):
        return self.first or self.mood_face


# ---------------------------------------------------------------- 清單與心情對照


def test_moods_map_to_the_models_own_expressions_with_fallbacks():
    assert mood_faces(["neutral", "joy", "sadness", "anger"]) == {
        "happy": "joy",
        "sad": "sadness",
        "angry": "anger",
        "worried": "sadness",
        "embarrassed": "joy",
        "calm": "neutral",
    }
    assert mood_faces(["neutral"]) == {"calm": "neutral"}


@needs_engine
def test_the_engine_gets_the_models_lists_and_mood_faces():
    choices = avatar_choices(_model())
    assert choices.expressions == ("neutral", "joy", "sadness")
    assert choices.motions == {"nod": "點頭", "wave": ""}
    assert choices.mood_faces["happy"] == "joy"


@needs_engine
def test_a_model_with_nothing_to_choose_from_gets_no_lists():
    assert avatar_choices(_model({"neutral": 0}, {})) is None
    assert avatar_choices(None) is None


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


def _agent(actions):
    return SimpleNamespace(reply_actions=lambda choices: actions)


def test_tags_mode_has_no_picker():
    assert picker_for(_character("tags"), _model(), _agent(_Actions())) is None


def test_a_character_without_the_setting_has_no_picker():
    character = _character("background")
    del character.expression_source
    assert picker_for(character, _model(), _agent(_Actions())) is None


def test_background_mode_without_a_background_model_stays_on_tags():
    assert (
        picker_for(
            _character("background", background=False), _model(), _agent(_Actions())
        )
        is None
    )


@needs_engine
def test_an_agent_that_is_not_the_engine_or_cannot_pick_has_no_picker():
    assert picker_for(_character("background"), _model(), SimpleNamespace()) is None
    assert picker_for(_character("background"), _model(), _agent(None)) is None
    assert (
        picker_for(_character("background"), _model(), _agent(_Actions(can_pick=False)))
        is None
    )


@needs_engine
def test_background_mode_asks_the_engine_with_the_models_lists():
    asked = []
    agent = SimpleNamespace(
        reply_actions=lambda choices: asked.append(choices) or _Actions()
    )
    picker = picker_for(_character("background"), _model(), agent)
    assert isinstance(picker, EnginePicker)
    assert asked[0].expressions == ("neutral", "joy", "sadness")


@needs_engine
def test_uses_background_expressions_follows_the_same_rule():
    assert expression_pick.uses_background_expressions(_character("background"))
    assert not expression_pick.uses_background_expressions(_character("tags"))
    assert not expression_pick.uses_background_expressions(
        _character("background", background=False)
    )


def test_an_engine_too_old_to_pick_keeps_the_tags(monkeypatch):
    """引擎 1.2.0 沒有 reply_actions：提示照舊教標籤，不然一個表情都沒有。"""
    import sys

    monkeypatch.setitem(sys.modules, "ai_character_engine.companion", None)
    assert not expression_pick.uses_background_expressions(_character("background"))


def test_an_agent_other_than_the_engine_keeps_the_tags():
    character = _character("background")
    character.agent_config.conversation_agent_choice = "letta_agent"
    assert not expression_pick.uses_background_expressions(character)


def test_the_engines_pick_comes_back_as_tomoshibi_reads_it():
    picker = EnginePicker(_Actions(("sadness", "nod", 0.4)))
    assert asyncio.run(picker.ask("今天好累。")) == {
        "expression": "sadness",
        "motion": "nod",
        "intensity": 0.4,
    }
    assert picker.voice_emotion() == "sadness"
    assert asyncio.run(EnginePicker(_Actions(None)).ask("…")) is None


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


def _picker(actions):
    return EnginePicker(actions)


def test_each_line_gets_its_pick_in_its_own_payload(monkeypatch):
    def by_line(line):
        return ("sadness", None, 0.5) if "好累" in line else ("joy", "nod", 1.0)

    actions = _Actions(by_line)
    messages = _run(
        monkeypatch,
        [("你來啦！", "你來啦！"), ("今天好累。", "今天好累。")],
        _picker(actions),
    )

    assert [m["actions"]["expressions"] for m in messages] == [[3], [1]]
    assert messages[0]["actions"]["motions"] == [{"group": "", "index": 1}]
    assert "motions" not in messages[1]["actions"]
    assert [m["audio"] for m in messages] == [
        "AUDIO:你來啦！.wav",
        "AUDIO:今天好累。.wav",
    ]
    assert actions.lines == ["你來啦！", "今天好累。"]


def test_no_pick_leaves_the_voice_playing(monkeypatch):
    (message,) = _run(monkeypatch, [("你來啦！", "你來啦！")], _picker(_Actions(None)))
    assert message["audio"] == "AUDIO:你來啦！.wav"
    assert "expressions" not in (message["actions"] or {})


def test_the_pick_runs_while_the_voice_is_made(monkeypatch):
    """合成 0.3 秒、挑選 0.3 秒：並行的話一句大約 0.3 秒，不是 0.6。"""
    started = time.monotonic()
    _run(
        monkeypatch,
        [("你來啦！", "你來啦！")],
        _picker(_Actions(delay=0.3)),
        engine=_Engine(delay=0.3),
    )
    assert time.monotonic() - started < 0.55


def test_a_silent_line_gets_a_pick_too(monkeypatch):
    (message,) = _run(monkeypatch, [("*歪頭*", "")], _picker(_Actions()))
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


# ---------------------------------------------------------------- 不擋聲音、語氣


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
    started = time.monotonic()
    (message,) = _run(
        monkeypatch,
        [("你來啦！", "你來啦！")],
        _picker(_Actions(delay=3.0)),
        engine=_Engine(delay=0.1),
    )
    assert time.monotonic() - started < 0.1 + expression_pick.GRACE_SECONDS + 0.3
    assert message["audio"] == "AUDIO:你來啦！.wav"
    assert "expressions" not in (message["actions"] or {})


def test_a_silent_line_waits_only_a_moment_for_its_pick(monkeypatch):
    started = time.monotonic()
    (message,) = _run(monkeypatch, [("*歪頭*", "")], _picker(_Actions(delay=3.0)))
    assert time.monotonic() - started < expression_pick.SILENT_GRACE_SECONDS + 0.3
    assert "expressions" not in (message["actions"] or {})


def test_the_voice_takes_her_mood_before_anything_is_picked(monkeypatch):
    engine = _Voiced()
    _run(
        monkeypatch,
        [("今天好累。", "今天好累。")],
        _picker(_Actions(delay=3.0, mood_face="sadness")),
        engine=engine,
    )
    assert engine.emotions == ["sadness"]


def test_the_first_pick_sets_the_voice_for_the_rest_of_the_reply(monkeypatch):
    """跟標籤一樣：這則回覆第一個挑到的表情，就是後面幾句的語氣。"""
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )
    engine = _Voiced(delay=0.2)
    picker = _picker(_Actions(delay=0.05, mood_face="sadness"))

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


# ---------------------------------------------------------------- 講這句時挑下一句


class _Overlap(_Actions):
    """記下同一時間有幾句在挑。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.now = 0
        self.most = 0

    async def pick(self, line):
        self.now += 1
        self.most = max(self.most, self.now)
        try:
            return await super().pick(line)
        finally:
            self.now -= 1


def _lasting(seconds_by_text):
    """假的 payload，帶著念完要多久（volumes × slice_length）。"""

    def prepare(audio_path, **kwargs):
        payload = _fake_prepare_audio_payload(audio_path, **kwargs)
        text = kwargs["display_text"].text
        seconds = seconds_by_text.get(text, 0.0)
        payload["slice_length"] = 50
        payload["volumes"] = [0.5] * int(seconds * 20)
        return payload

    return prepare


def _run_lasting(monkeypatch, lines, picker, seconds_by_text):
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _lasting(seconds_by_text)
    )

    async def go():
        manager = TTSTaskManager()
        send = _Send()
        started = time.monotonic()
        await handle_sentence_output(
            _Sentences(lines),
            live2d_model=_model(),
            tts_engine=_Engine(delay=0.05),
            websocket_send=send,
            tts_manager=manager,
            expression_picker=picker,
        )
        await asyncio.gather(*manager.task_list)
        await manager._payload_queue.join()
        return send.messages, time.monotonic() - started

    return asyncio.run(go())


def test_lines_are_picked_one_after_another_and_none_is_dropped(monkeypatch):
    actions = _Overlap(delay=0.1)
    lines = [
        ("你來啦！", "你來啦！"),
        ("今天好累。", "今天好累。"),
        ("要喝茶嗎？", "要喝茶嗎？"),
    ]
    messages, _ = _run_lasting(
        monkeypatch, lines, _picker(actions), {"你來啦！": 1.0, "今天好累。": 1.0}
    )
    assert actions.most == 1
    assert actions.lines == ["你來啦！", "今天好累。", "要喝茶嗎？"]
    assert all(m["actions"]["expressions"] == [3] for m in messages)


def test_a_later_line_is_picked_while_the_line_before_plays(monkeypatch):
    """第一句念 1.5 秒：第二句的挑選有 1 秒可用，不是只有合成後的 0.3 秒。"""
    messages, took = _run_lasting(
        monkeypatch,
        [("你來啦！", "你來啦！"), ("今天好累。", "今天好累。")],
        _picker(_Actions(delay=0.6)),
        {"你來啦！": 1.5},
    )
    assert "expressions" not in (messages[0]["actions"] or {})  # 第一句照舊只等一下
    assert messages[1]["actions"]["expressions"] == [3]
    assert took < 1.5


def test_a_pick_given_up_on_does_not_hold_up_the_next_line(monkeypatch):
    actions = _Actions(lambda line: ("joy", None, 1.0))
    slow = {"你來啦！": 3.0}

    async def pick(line):
        actions.lines.append(line)
        await asyncio.sleep(slow.get(line, 0.1))
        return SimpleNamespace(expression="joy", motion=None, intensity=1.0)

    actions.pick = pick
    messages, took = _run_lasting(
        monkeypatch,
        [("你來啦！", "你來啦！"), ("今天好累。", "今天好累。")],
        _picker(actions),
        {"你來啦！": 1.0},
    )
    assert "expressions" not in (messages[0]["actions"] or {})
    assert messages[1]["actions"]["expressions"] == [3]
    assert took < 1.5


def test_waiting_for_the_lines_before_does_not_spin(monkeypatch):
    """前面的句子還沒送出時，這句是睡著等，不是一直空轉。"""
    import src.open_llm_vtuber.conversations.tts_manager as module

    rounds = []
    real_wait = module.asyncio.wait

    async def counting_wait(*args, **kwargs):
        rounds.append(1)
        return await real_wait(*args, **kwargs)

    monkeypatch.setattr(module.asyncio, "wait", counting_wait)
    _run_lasting(
        monkeypatch,
        [("你來啦！", "你來啦！"), ("今天好累。", "今天好累。")],
        _picker(_Actions(delay=0.4)),
        {"你來啦！": 1.0},
    )
    assert len(rounds) < 20
