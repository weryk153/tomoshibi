"""ASR 還原：語音那一輪先用上下文把同音錯字還原，她讀到的就是還原後的字。

9B 模型看到「空尼七哇」會當成使用者真的那樣唸、去評他的發音；提示壓不住。
所以在她回話之前就把字還原，她根本看不到錯字。沒把握、太慢、壞掉都用原文。
"""

import asyncio
import json
from types import SimpleNamespace

import numpy as np
import pytest

from src.open_llm_vtuber import asr_repair
from src.open_llm_vtuber.asr_repair import RepairResult, accept, repair
from src.open_llm_vtuber.config_manager.asr import ASRConfig
from src.open_llm_vtuber.conversations import (
    conversation_utils,
    single_conversation,
)

AUDIO = np.zeros(1600, dtype=np.float32)
TRANSCRIPT = [
    ("User", "教我日文"),
    ("Pekora", "打招呼的時候說「こんにちは」，跟著我念！"),
]
LANGS = ("Traditional Chinese (Taiwan)", "Japanese")


class FakeClient:
    def __init__(self, reply="", *, delay=0.0, error=None):
        self.reply = reply
        self.delay = delay
        self.error = error
        self.calls = []

    async def complete(self, messages):
        self.calls.append(messages)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.reply


def _reply(text, confidence, note="同音"):
    return json.dumps({"text": text, "confidence": confidence, "note": note})


def _run(raw, client, **kwargs):
    return asyncio.run(
        repair(raw, TRANSCRIPT, client=client, languages=LANGS, **kwargs)
    )


# --- accept()：採用守門 -------------------------------------------------------------


def test_accepts_a_confident_same_length_fix():
    assert accept("空尼七哇", "こんにちは", 0.9)


def test_rejects_low_confidence():
    assert not accept("空尼七哇", "こんにちは", 0.69)
    assert accept("空尼七哇", "こんにちは", 0.7)


def test_rejects_an_empty_fix():
    assert not accept("空尼七哇", "", 0.95)
    assert not accept("空尼七哇", "  ", 0.95)


def test_rejects_a_fix_much_shorter_or_longer():
    assert not accept("我說用講的不是打字", "講", 0.95)  # < 0.5
    assert not accept("太暖的", "太難的，從簡單的開始好嗎", 0.95)  # > 2.0
    assert accept("太暖的", "太難的", 0.95)


def test_rejects_a_one_character_input():
    assert not accept("啊", "阿", 0.95)


def test_rejects_a_catchphrase_only_input():
    assert not accept("konpeko！", "こんぺこ！", 0.95, catchphrases=["konpeko"])
    assert accept("空尼七哇", "こんにちは", 0.95, catchphrases=["konpeko"])


def test_rejects_a_punctuation_only_change():
    assert not accept("繼續。", "繼續", 0.95)
    assert not accept("お願い。", "お願い", 0.95)


def test_a_chinese_to_chinese_fix_keeps_one_character_per_syllable():
    # 同音字是一個字換一個字；字數變了就是潤飾或改寫。
    assert accept("我說用降的不是打字", "我說用講的不是打字", 0.95)
    assert accept("太暖的，從簡單的開始。", "太難的，從簡單的開始。", 0.95)
    assert not accept(
        "你哪時候在女僕咖啡廳打工？", "你什麼時候在女僕咖啡廳打工？", 0.95
    )
    assert not accept("什麼聽不懂。", "什麼都聽不懂。", 0.95)
    # 寫成假名的外語不受這條限制。
    assert accept("歐嗨唷狗紮伊媽斯", "おはようございます", 0.95)


def test_rejects_a_fix_that_changes_the_numbers():
    assert not accept("先從50音", "先從五十音", 0.95)
    assert accept("給我3個空尼七哇", "給我3個こんにちは", 0.95)


def test_rejects_a_change_of_character_form_only():
    # 繁簡／日文字形的換字不是還原，是改了使用者的寫法。
    assert not accept("私は人參が好きです。", "私は人参が好きです。", 0.95)
    assert not accept("歐嗨唷狗紮伊媽斯", "歐嗨唷狗扎伊媽斯", 0.95)
    assert not accept("無職轉生", "無職転生", 0.95)


def test_kana_must_sound_like_the_characters_it_replaces():
    # 中文諧音換成假名：一個字一個音節，假名不會多出一大截。多出來的是翻譯。
    assert accept("空尼七哇", "こんにちは", 0.95)
    assert accept("咋嬌娜娜", "さようなら", 0.95)
    assert accept("歐嗨唷狗紮伊媽斯", "おはようございます", 0.95)
    assert not accept("你是 AI 嗎？", "あなたは AI ですか？", 0.95)
    assert not accept("謝謝你", "ありがとうございます", 0.95)


def test_kana_for_chinese_sound_alikes_must_come_from_the_conversation():
    # 中文諧音換成假名，只在她剛講過那句日文時才算（教學、跟讀）。
    said = "打招呼的時候說「こんにちは」，跟著本小姐念一次！"
    assert accept("空尼七哇", "こんにちは", 0.95, context=said)
    assert not accept("哈囉", "ハロー", 0.95, context="")
    assert not accept("哈囉", "ハロー", 0.95, context=said)
    # 假名換假名不受這條限制。
    assert accept("こんめんには。", "こんにちは。", 0.95, context="")


def test_rejects_a_fix_that_copies_an_earlier_user_line():
    earlier = ["什麼甜點", "那你會煮了嗎"]
    assert not accept("等下班", "什麼甜點", 0.95, earlier=earlier)
    assert accept("太暖的", "太難的", 0.95, earlier=earlier)


def test_the_length_ratio_bounds_are_inclusive():
    assert accept("abcdefgh", "abcd", 0.95)  # 0.5
    assert not accept("abcdefgh", "abc", 0.95)
    assert accept("ab", "abcd", 0.95)  # 2.0
    assert not accept("ab", "abcde", 0.95)


def test_a_chinese_fix_must_sound_like_what_it_replaces():
    # 字數一樣也可能改了意思：換掉的字要同音或近音。
    assert not accept("我不要吃飯", "我也要吃飯", 0.95)
    assert not accept("你是 AI 嗎？", "你是 AI 吧？", 0.95)
    assert not accept("你打疫苗關現也不舒服。", "你打疫苗現在也不舒服。", 0.95)
    assert accept("太暖的", "太難的", 0.95)  # nuan／nan
    assert accept("叫我日文", "教我日文", 0.95)  # 同音
    assert accept("我是說四十", "我是說是時", 0.95)  # 平翹舌不分


def test_at_most_two_chinese_characters_change():
    assert accept("期中考", "其終考", 0.95)
    assert not accept("期中考", "其終烤", 0.95)


def test_latin_letters_do_not_switch_off_the_chinese_rules():
    assert not accept("用 ASR 說的什麼聽不懂", "用 ASR 說的什麼都聽不懂", 0.95)
    assert not accept("我不要 coffee", "我也要 coffee", 0.95)
    assert accept("用 ASR 說太暖了", "用 ASR 說太難了", 0.95)


def test_kana_is_counted_in_morae():
    # 拗音、促音、長音不算一拍：きょう 是兩拍。
    assert accept("給我寇", "給我コー", 0.95)
    assert accept("給我寇寇", "給我きょきょ", 0.95)
    assert not accept("給我寇", "給我コーヒー", 0.95)


def test_romaji_can_become_the_kana_she_taught():
    said = "跟著我念「こんにちは」！"
    assert accept("konnichiwa", "こんにちは", 0.95, context=said)
    assert accept("ohayou gozaimasu", "おはようございます", 0.95)
    assert not accept("thank you", "ありがとう", 0.95, context=said)


def test_she_may_ask_for_the_line_the_user_already_said():
    # 跟讀重來：使用者上一句已經被還原成「こんにちは」，她又要他再念一次。
    said = "再念一次「こんにちは」！"
    assert accept(
        "空尼七哇",
        "こんにちは",
        0.95,
        earlier=["こんにちは"],
        her_lines=[said],
        context=said,
    )
    assert not accept(
        "空尼七哇", "こんにちは", 0.95, earlier=["こんにちは"], her_lines=["好"]
    )


# --- repair() --------------------------------------------------------------------


def test_repair_uses_the_fix_when_it_passes():
    client = FakeClient(_reply("こんにちは", 0.92))
    result = _run("空尼七哇", client)
    assert result == RepairResult(
        text="こんにちは", changed=True, confidence=0.92, reason="同音"
    )
    prompt = "\n".join(m["content"] for m in client.calls[0])
    assert "空尼七哇" in prompt
    assert "教我日文" in prompt and "Pekora" in prompt
    assert "Japanese" in prompt


def test_the_new_line_is_marked_apart_from_the_conversation():
    client = FakeClient(_reply("空尼七哇", 0.2))
    _run("空尼七哇", client)
    user = client.calls[0][-1]["content"]
    assert user.rstrip().endswith("New line from ASR:\n空尼七哇")
    assert user.index("教我日文") < user.index("空尼七哇")


def test_quotes_the_model_put_around_the_line_are_dropped():
    assert (
        _run("空尼七哇", FakeClient(_reply("「こんにちは」", 0.9))).text == "こんにちは"
    )
    kept = _run("他說「好」", FakeClient(_reply("他說「好」", 0.9)))
    assert kept.text == "他說「好」"


def test_repair_will_not_copy_an_earlier_user_line():
    client = FakeClient(_reply("教我日文", 0.95))
    result = asyncio.run(
        repair("叫我日文", TRANSCRIPT, client=client, languages=LANGS, user="User")
    )
    assert result.text == "叫我日文"
    assert not result.changed


def test_repair_lets_her_ask_for_a_repeat():
    transcript = [("User", "こんにちは"), ("Pekora", "再念一次「こんにちは」！")]
    result = asyncio.run(
        repair(
            "空尼七哇",
            transcript,
            client=FakeClient(_reply("こんにちは", 0.95)),
            languages=LANGS,
            user="User",
        )
    )
    assert result.text == "こんにちは"


def test_repair_keeps_the_original_on_low_confidence():
    result = _run("空尼七哇", FakeClient(_reply("こんにちは", 0.4)))
    assert result.text == "空尼七哇"
    assert not result.changed
    assert result.confidence == 0.4


def test_repair_keeps_the_original_on_timeout():
    client = FakeClient(_reply("こんにちは", 0.9), delay=1.0)
    result = _run("空尼七哇", client, timeout=0.05)
    assert result.text == "空尼七哇"
    assert not result.changed


def test_repair_keeps_the_original_on_bad_json():
    for reply in ("こんにちは", "{not json", json.dumps({"confidence": 0.9}), "[]"):
        result = _run("空尼七哇", FakeClient(reply))
        assert result.text == "空尼七哇"
        assert not result.changed


def test_repair_keeps_the_original_when_the_call_fails():
    result = _run("空尼七哇", FakeClient(error=RuntimeError("down")))
    assert result.text == "空尼七哇"
    assert not result.changed


def test_repair_reads_json_inside_a_code_fence():
    reply = "```json\n" + _reply("こんにちは", 0.9) + "\n```"
    assert _run("空尼七哇", FakeClient(reply)).text == "こんにちは"


def test_an_unchanged_reply_is_not_a_change():
    result = _run("我想學日文", FakeClient(_reply("我想學日文", 0.95)))
    assert result.text == "我想學日文"
    assert not result.changed


def test_a_catchphrase_only_line_is_not_sent():
    client = FakeClient(_reply("こんぺこ", 0.95))
    result = _run("konpeko！", client, catchphrases=["konpeko"])
    assert result.text == "konpeko！"
    assert not result.changed
    assert client.calls == []


def test_a_one_character_line_is_not_sent():
    client = FakeClient(_reply("阿", 0.95))
    assert _run("啊", client).text == "啊"
    assert client.calls == []


# --- 開關與設定 --------------------------------------------------------------------


def test_the_switch_is_on_by_default():
    config = ASRConfig(asr_model="sherpa_onnx_asr")
    assert config.repair_with_context is True
    off = ASRConfig(asr_model="sherpa_onnx_asr", repair_with_context=False)
    assert off.repair_with_context is False


def _context(*, switch=True, base_url="http://127.0.0.1:1234/v1", model="qwen"):
    engine = SimpleNamespace(
        background_base_url=base_url, background_model=model, background_api_key=""
    )
    llm = SimpleNamespace(
        llm_api_key="key", extra_body={"reasoning_effort": "none", "top_p": 0.8}
    )
    return SimpleNamespace(
        history_uid="h1",
        system_config=SimpleNamespace(player_language="Traditional Chinese (Taiwan)"),
        character_config=SimpleNamespace(
            conf_uid="pekora",
            character_name="Pekora",
            human_name="me",
            reply_language="",
            catchphrases={"konpeko": "こんぺこ"},
            tts_config=SimpleNamespace(
                tts_model="gpt_sovits_tts",
                gpt_sovits_tts=SimpleNamespace(text_lang="all_ja"),
            ),
            asr_config=SimpleNamespace(repair_with_context=switch),
            agent_config=SimpleNamespace(
                agent_settings=SimpleNamespace(
                    character_engine_agent=engine,
                    conversation=SimpleNamespace(llm_provider="lmstudio_llm"),
                ),
                llm_configs=SimpleNamespace(lmstudio_llm=llm),
            ),
        ),
    )


def test_no_repairer_when_switched_off():
    assert asr_repair.repairer(_context(switch=False)) is None


def test_no_repairer_without_a_background_model():
    assert asr_repair.repairer(_context(base_url="")) is None
    assert asr_repair.repairer(_context(model="")) is None


def test_the_repairer_reads_the_conversation_and_languages(monkeypatch):
    seen = {}

    async def fake_repair(text, transcript, *, client, languages, catchphrases, user):
        seen.update(
            user=user,
            text=text,
            transcript=transcript,
            client=client,
            languages=languages,
            catchphrases=list(catchphrases),
        )
        return RepairResult("こんにちは", True, 0.9, "同音")

    history = [
        {"role": "metadata", "content": ""},
        {"role": "human", "content": "教我日文", "name": "me"},
        {"role": "ai", "content": "", "name": "Pekora"},
        {"role": "system", "content": "[Interrupted by user]"},
        {"role": "ai", "content": "跟著我念", "name": "Pekora"},
    ]
    monkeypatch.setattr(asr_repair, "get_history", lambda conf, uid: history[1:])
    monkeypatch.setattr(asr_repair, "repair", fake_repair)

    fix = asr_repair.repairer(_context())
    assert asyncio.run(fix("空尼七哇")) == "こんにちは"
    assert seen["text"] == "空尼七哇"
    assert seen["transcript"] == [("me", "教我日文"), ("Pekora", "跟著我念")]
    assert seen["languages"] == ("Traditional Chinese (Taiwan)", "Japanese")
    assert seen["catchphrases"] == ["konpeko"]
    assert seen["user"] == "me"
    assert seen["client"].base_url == "http://127.0.0.1:1234/v1"
    assert seen["client"].model == "qwen"
    assert seen["client"].api_key == "key"
    # 只帶思考開關，不帶取樣參數；temperature 0。
    assert seen["client"].request_options == {
        "temperature": 0,
        "max_tokens": asr_repair.MAX_TOKENS,
        "reasoning_effort": "none",
    }


def test_the_transcript_keeps_only_the_last_six_rounds(monkeypatch):
    history = []
    for i in range(10):
        history.append({"role": "human", "content": f"u{i}", "name": "me"})
        history.append({"role": "ai", "content": f"a{i}", "name": "Pekora"})
    monkeypatch.setattr(asr_repair, "get_history", lambda conf, uid: history)
    lines = asr_repair.recent_transcript(_context())
    assert len(lines) == 12
    assert lines[0] == ("me", "u4")
    assert lines[-1] == ("Pekora", "a9")


def test_older_lines_are_cut_shorter_than_the_last_two():
    long = "哈" * 200
    history = [
        {"role": "human", "content": "u0", "name": "me"},
        {"role": "ai", "content": long, "name": "Pekora"},
        {"role": "human", "content": "u1", "name": "me"},
        {"role": "ai", "content": long + "跟著我念", "name": "Pekora"},
    ]
    lines = asr_repair.transcript_from(history, "me", "Pekora")
    assert lines[1][1] == "…" + "哈" * asr_repair.OLDER_LINE_CHARS
    # 她最後一句的結尾（通常是要對方念的那句）留得比較長。
    assert lines[3][1].endswith("跟著我念")
    assert len(lines[3][1]) == asr_repair.LINE_CHARS + 1


def test_the_phrase_she_taught_survives_in_an_older_line():
    taught = "前" * 100 + "試著跟著我念：「さようなら」，意思是再見！" + "後" * 100
    history = [
        {"role": "ai", "content": taught, "name": "Pekora"},
        {"role": "human", "content": "咋嬌娜娜", "name": "me"},
        {"role": "ai", "content": "不對喔，" + "再" * 60, "name": "Pekora"},
        {"role": "human", "content": "什麼", "name": "me"},
    ]
    lines = asr_repair.transcript_from(history, "me", "Pekora")
    assert "「さようなら」" in lines[0][1]
    assert len(lines[0][1]) <= asr_repair.LINE_CHARS + 2
    # 沒有要念的句子的舊句子照樣只留結尾。
    assert len(lines[2][1]) <= asr_repair.LINE_CHARS + 1


def test_the_repairer_keeps_the_line_when_the_history_cannot_be_read(monkeypatch):
    def broken(conf_uid, history_uid):
        raise OSError("disk")

    monkeypatch.setattr(asr_repair, "get_history", broken)
    fix = asr_repair.repairer(_context())
    assert asyncio.run(fix("空尼七哇")) == "空尼七哇"


# --- process_user_input -----------------------------------------------------------


class _ASR:
    async def async_transcribe_np(self, audio):
        return "空尼七哇"


def _process(user_input, repair_fn):
    sent = []

    async def send(message):
        sent.append(json.loads(message))

    text = asyncio.run(
        conversation_utils.process_user_input(
            user_input, _ASR(), send, repair=repair_fn
        )
    )
    return text, sent


def test_a_spoken_line_is_repaired_before_anyone_sees_it():
    calls = []

    async def fix(text):
        calls.append(text)
        return "こんにちは"

    text, sent = _process(AUDIO, fix)
    assert calls == ["空尼七哇"]
    assert text == "こんにちは"
    assert sent == [{"type": "user-input-transcription", "text": "こんにちは"}]


def test_a_typed_line_is_never_repaired():
    calls = []

    async def fix(text):
        calls.append(text)
        return "x"

    text, sent = _process("空尼七哇", fix)
    assert text == "空尼七哇"
    assert calls == []
    assert sent == []


def test_without_a_repairer_the_line_is_untouched():
    text, sent = _process(AUDIO, None)
    assert text == "空尼七哇"
    assert sent == [{"type": "user-input-transcription", "text": "空尼七哇"}]


def test_an_interrupt_during_the_repair_keeps_the_line():
    sent, kept = [], []

    async def send(message):
        sent.append(json.loads(message))

    async def slow(text):
        await asyncio.sleep(10)
        return "こんにちは"

    async def main():
        task = asyncio.create_task(
            conversation_utils.process_user_input(
                AUDIO, _ASR(), send, repair=slow, on_cancelled=kept.append
            )
        )
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(main())
    assert sent == [{"type": "user-input-transcription", "text": "空尼七哇"}]
    assert kept == ["空尼七哇"]


# --- 單人對話 ---------------------------------------------------------------------


class _Stop(Exception):
    pass


def _single_turn(monkeypatch, user_input, *, switch=True):
    repaired = []
    made = []

    class _Fixer:
        async def __call__(self, text):
            repaired.append(text)
            return "こんにちは"

    monkeypatch.setattr(
        asr_repair,
        "repairer",
        lambda context: _Fixer()
        if context.character_config.asr_config.repair_with_context
        else None,
    )

    async def nothing(*_args, **_kwargs):
        return None

    def capture(**kwargs):
        made.append(kwargs)
        raise _Stop

    monkeypatch.setattr(single_conversation, "send_conversation_start_signals", nothing)
    monkeypatch.setattr(single_conversation, "create_batch_input", capture)
    monkeypatch.setattr(single_conversation, "cleanup_conversation", lambda *a: None)

    context = _context(switch=switch)
    context.agent_engine = object()
    context.asr_engine = _ASR()
    context.history_uid = ""
    with pytest.raises(_Stop):
        asyncio.run(
            single_conversation.process_single_conversation(
                context, nothing, "client", user_input
            )
        )
    return made[0], repaired


def test_a_spoken_single_turn_reaches_her_repaired(monkeypatch):
    made, repaired = _single_turn(monkeypatch, AUDIO)
    assert repaired == ["空尼七哇"]
    assert made["input_text"] == "こんにちは"
    assert made["metadata"]["spoken_text"] == "こんにちは"


def test_a_typed_single_turn_is_not_repaired(monkeypatch):
    made, repaired = _single_turn(monkeypatch, "空尼七哇")
    assert repaired == []
    assert made["input_text"] == "空尼七哇"


def test_a_spoken_single_turn_with_the_switch_off_is_not_repaired(monkeypatch):
    made, repaired = _single_turn(monkeypatch, AUDIO, switch=False)
    assert repaired == []
    assert made["input_text"] == "空尼七哇"


# --- 群組對話 ---------------------------------------------------------------------


def test_a_spoken_group_line_is_repaired_once_for_everyone(monkeypatch):
    from src.open_llm_vtuber.conversations import group_conversation

    broadcast = []

    async def fix(text):
        return "こんにちは"

    async def send(_message):
        return None

    async def record(*args, **kwargs):
        broadcast.append(args)

    monkeypatch.setattr(asr_repair, "repairer", lambda context: fix)
    monkeypatch.setattr(group_conversation, "broadcast_transcription", record)
    context = _context()
    context.asr_engine = _ASR()
    text = asyncio.run(
        group_conversation.process_group_input(
            user_input=AUDIO,
            initiator_context=context,
            initiator_ws_send=send,
            broadcast_func=send,
            group_members=["a", "b"],
            initiator_client_uid="a",
        )
    )
    assert text == "こんにちは"
    assert broadcast and broadcast[0][2] == "こんにちは"


def test_an_interrupted_single_turn_still_records_what_was_said(monkeypatch):
    stored = []

    async def interrupted(text):
        raise asyncio.CancelledError

    async def nothing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(asr_repair, "repairer", lambda context: interrupted)
    monkeypatch.setattr(single_conversation, "send_conversation_start_signals", nothing)
    monkeypatch.setattr(single_conversation, "cleanup_conversation", lambda *a: None)
    monkeypatch.setattr(
        single_conversation, "store_message", lambda **kw: stored.append(kw)
    )
    context = _context()
    context.agent_engine = object()
    context.asr_engine = _ASR()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(
            single_conversation.process_single_conversation(
                context, nothing, "client", AUDIO
            )
        )
    assert [(m["role"], m["content"]) for m in stored] == [("human", "空尼七哇")]
