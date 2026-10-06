"""翻譯審核（背景）：她每句語音翻譯事後由背景模型審一遍，累積成建議清單。

不改當下輸出、不加延遲；開關關著時完全不跑。
"""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.config_manager.character import CharacterConfig
from src.open_llm_vtuber.conversations import tts_manager as tts_manager_module
from src.open_llm_vtuber.conversations.conversation_utils import (
    handle_sentence_output,
    process_agent_output,
)
from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager
from src.open_llm_vtuber.translate import audit
from src.open_llm_vtuber.translate.audit import (
    AuditStore,
    TranslationAuditor,
    parse_reply,
)
from src.open_llm_vtuber.utils.stream_audio import prepare_audio_payload


class FakeClient:
    """記下每次呼叫；回覆照 replies 依序給（不夠就重複最後一個）。"""

    def __init__(self, *replies, delay=0.0, error=None):
        self.replies = list(replies) or ['{"results": []}']
        self.calls: list[list[dict]] = []
        self.delay = delay
        self.error = error

    async def complete(self, messages):
        self.calls.append(messages)
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        index = min(len(self.calls), len(self.replies)) - 1
        return self.replies[index]


def _ok(n):
    return json.dumps(
        {"results": [{"i": i + 1, "ok": True, "issues": []} for i in range(n)]}
    )


def _auditor(tmp_path, client, **kwargs):
    return TranslationAuditor(
        client, AuditStore(tmp_path / "audit"), character="佩克拉", **kwargs
    )


def _lines(tmp_path):
    path = tmp_path / "audit" / "audit.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()]


def _summary(tmp_path):
    return json.loads((tmp_path / "audit" / "summary.json").read_text("utf-8"))


# ---------------------------------------------------------------- 解析


def test_parse_keeps_known_kinds_only():
    reply = json.dumps(
        {
            "results": [
                {
                    "i": 1,
                    "ok": False,
                    "issues": [
                        {"kind": "omitted", "detail": "dropped 'today'"},
                        {"kind": "style", "detail": "too formal"},
                        {"kind": "name"},
                        "garbage",
                    ],
                }
            ]
        }
    )
    (result,) = parse_reply(reply, 1)
    assert result["issues"] == [
        {"kind": "omitted", "detail": "dropped 'today'"},
        {"kind": "name", "detail": ""},
    ]
    assert result["ok"] is False


def test_parse_reads_fenced_json_and_a_bare_list():
    reply = '```json\n[{"ok": true, "issues": []}, {"ok": true}]\n```'
    results = parse_reply(reply, 2)
    assert [r["ok"] for r in results] == [True, True]


def test_parse_matches_results_by_number():
    reply = json.dumps(
        {
            "results": [
                {"i": 2, "ok": False, "issues": [{"kind": "meaning", "detail": "x"}]},
                {"i": 9, "ok": False, "issues": [{"kind": "meaning", "detail": "y"}]},
            ]
        }
    )
    first, second = parse_reply(reply, 2)
    assert first is None
    assert second["issues"][0]["detail"] == "x"


def test_parse_rejects_unreadable_replies():
    assert parse_reply("not json", 2) is None
    assert parse_reply('{"text": "hi"}', 2) is None
    assert parse_reply("", 1) is None


def test_issues_make_a_line_not_ok():
    reply = json.dumps(
        {"results": [{"ok": True, "issues": [{"kind": "added", "detail": "x"}]}]}
    )
    (result,) = parse_reply(reply, 1)
    assert result["ok"] is False


# ---------------------------------------------------------------- 批次與佇列


def test_submit_only_queues_and_flush_sends_batches_of_four(tmp_path):
    """句子一句一句進來時不問模型（主模型還在講）；一輪結束才一批一批審。"""
    client = FakeClient(_ok(4), _ok(2))
    auditor = _auditor(tmp_path, client)
    for n in range(6):
        auditor.submit(f"句{n}", f"文{n}", "ja")
    assert client.calls == []

    asyncio.run(auditor.flush())
    assert len(client.calls) == 2
    first = client.calls[0][-1]["content"]
    assert all(f"句{n}" in first and f"文{n}" in first for n in range(4))
    assert "句4" not in first
    assert [line["original"] for line in _lines(tmp_path)] == [
        f"句{n}" for n in range(6)
    ]


def test_flush_with_nothing_queued_does_not_call(tmp_path):
    client = FakeClient(_ok(2))
    auditor = _auditor(tmp_path, client)

    async def run():
        auditor.submit("句0", "文0", "ja")
        auditor.submit("句1", "文1", "ja")
        await auditor.flush()
        await auditor.flush()  # 空的佇列不呼叫

    asyncio.run(run())
    assert len(client.calls) == 1
    assert len(_lines(tmp_path)) == 2


def test_lines_queued_during_a_slow_flush_keep_the_newest_eight(tmp_path):
    """模型還在審上一批時進來的句子排隊；超過上限丟最舊的。"""
    client = FakeClient(_ok(4), delay=0.05)
    auditor = _auditor(tmp_path, client)

    async def run():
        for n in range(4):
            auditor.submit(f"前{n}", f"x{n}", "ja")
        busy = asyncio.create_task(auditor.flush())
        await asyncio.sleep(0.01)  # 第一批已經送出去，模型還沒回
        assert len(client.calls) == 1
        for n in range(12):
            auditor.submit(f"後{n}", f"y{n}", "ja")
        await busy
        await auditor.flush()

    asyncio.run(run())
    originals = [line["original"] for line in _lines(tmp_path)]
    assert originals[:4] == [f"前{n}" for n in range(4)]
    assert originals[4:] == [f"後{n}" for n in range(4, 12)]


def test_submit_drops_the_oldest_when_full(tmp_path):
    auditor = _auditor(tmp_path, FakeClient(_ok(4)))
    for n in range(10):
        auditor.submit(f"句{n}", f"文{n}", "ja")
    assert [item.original for item in auditor._queue] == [
        f"句{n}" for n in range(2, 10)
    ]


# ---------------------------------------------------------------- 失敗不炸


@pytest.mark.parametrize(
    "client",
    [
        FakeClient("this is not json"),
        FakeClient('{"results": "nope"}'),
        FakeClient(error=RuntimeError("connection refused")),
    ],
)
def test_bad_replies_and_errors_are_dropped_quietly(tmp_path, client):
    auditor = _auditor(tmp_path, client)

    async def run():
        auditor.submit("句", "文", "ja")
        await auditor.flush()

    asyncio.run(run())
    assert _lines(tmp_path) == []
    assert len(auditor._queue) == 0


def test_timeout_is_dropped_quietly(tmp_path):
    client = FakeClient(_ok(1), delay=1.0)
    auditor = _auditor(tmp_path, client, timeout=0.01)

    async def run():
        auditor.submit("句", "文", "ja")
        await auditor.flush()

    asyncio.run(run())
    assert _lines(tmp_path) == []


# ---------------------------------------------------------------- 存檔與加總


def _flagged_reply():
    return json.dumps(
        {
            "results": [
                {
                    "i": 1,
                    "ok": False,
                    "issues": [
                        {"kind": "name", "detail": "ぺこら written as ペコラ"},
                        {"kind": "catchphrase", "detail": "peko dropped"},
                    ],
                    "suggest": {
                        "protected_names": {"ペコラ": "ぺこら"},
                        "catchphrases": {"peko": "ぺこ"},
                    },
                },
                {"i": 2, "ok": True, "issues": []},
            ]
        }
    )


def test_summary_counts_suggestions_and_keeps_suspicious_lines(tmp_path):
    client = FakeClient(_flagged_reply())
    auditor = _auditor(tmp_path, client)

    async def run():
        for _ in range(2):
            auditor.submit("佩克拉今天也很好peko", "ペコラは今日も元気", "ja")
            auditor.submit("你好", "こんにちは", "ja")
            await auditor.flush()

    asyncio.run(run())
    summary = _summary(tmp_path)
    assert summary["audited"] == 4
    assert summary["flagged"] == 2
    assert summary["protected_names"] == {"ペコラ": {"ぺこら": 2}}
    assert summary["catchphrases"] == {"peko": {"ぺこ": 2}}
    assert len(summary["suspicious"]) == 2
    line = summary["suspicious"][-1]
    assert line["original"] == "佩克拉今天也很好peko"
    assert line["translated"] == "ペコラは今日も元気"
    assert line["issues"][0]["kind"] == "name"
    assert "time" in line
    logged = _lines(tmp_path)
    assert len(logged) == 4
    assert logged[1]["issues"] == []


def test_suggestions_must_point_at_the_lines(tmp_path):
    """名字的錯誤寫法要真的出現在譯句裡，口頭禪要真的出現在原句裡。"""
    reply = json.dumps(
        {
            "results": [
                {
                    "ok": False,
                    "issues": [{"kind": "name", "detail": "x"}],
                    "suggest": {
                        "protected_names": {"岡部": "岡部", "ロボ": "ろぼ"},
                        "catchphrases": {"nya": "にゃ", "": "x"},
                    },
                }
            ]
        }
    )
    auditor = _auditor(tmp_path, FakeClient(reply))

    async def run():
        auditor.submit("今天天氣很好", "今日はいい天気", "ja")
        await auditor.flush()

    asyncio.run(run())
    summary = _summary(tmp_path)
    assert summary["protected_names"] == {}
    assert summary["catchphrases"] == {}


def test_suspicious_list_keeps_the_last_fifty(tmp_path):
    store = AuditStore(tmp_path / "audit")
    issue = [{"kind": "meaning", "detail": "x"}]
    for n in range(60):
        store.record(
            [
                {
                    "time": "t",
                    "original": f"句{n}",
                    "translated": "x",
                    "target_lang": "ja",
                    "issues": issue,
                    "suggest": {},
                }
            ]
        )
    summary = _summary(tmp_path)
    assert summary["flagged"] == 60
    assert len(summary["suspicious"]) == 50
    assert summary["suspicious"][0]["original"] == "句10"


def test_the_prompt_carries_the_characters_terms(tmp_path):
    client = FakeClient(_ok(1))
    auditor = _auditor(
        tmp_path,
        client,
        names=["兔田佩克拉"],
        catchphrases={"peko": "ぺこ"},
    )

    async def run():
        auditor.submit("句", "文", "ja")
        await auditor.flush()

    asyncio.run(run())
    prompt = client.calls[0][-1]["content"]
    assert "兔田佩克拉" in prompt
    assert "peko → ぺこ" in prompt
    assert "Japanese" in prompt


# ---------------------------------------------------------------- 開關


def _character(enabled=True, uid="pekora", base_url="http://x/v1", model="m"):
    engine = SimpleNamespace(
        background_base_url=base_url,
        background_model=model,
        background_api_key="",
    )
    settings = SimpleNamespace(
        character_engine_agent=engine,
        conversation=SimpleNamespace(llm_provider="lmstudio_llm"),
    )
    agent = SimpleNamespace(agent_settings=settings, llm_configs=SimpleNamespace())
    return SimpleNamespace(
        conf_uid=uid,
        character_name="佩克拉",
        translation_audit=enabled,
        agent_config=agent,
        protected_names={"兔田佩克拉": ["兔田佩可拉"]},
        catchphrases={"peko": "ぺこ"},
    )


def test_auditor_only_when_switched_on_and_a_background_model_exists(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    audit.reset()
    assert audit.auditor_for(_character(enabled=False)) is None
    assert audit.auditor_for(_character(base_url="")) is None
    assert audit.auditor_for(_character(uid="")) is None
    one = audit.auditor_for(_character())
    assert one is not None
    assert audit.auditor_for(_character()) is one
    assert one.store.directory == Path("chat_history/pekora/translation_audit")
    assert one.names == ["兔田佩克拉"]
    assert one.catchphrases == {"peko": "ぺこ"}
    audit.reset()


def test_character_config_field_defaults_off():
    field = CharacterConfig.model_fields["translation_audit"]
    assert field.default is False
    assert field.alias == "translation_audit"


# ---------------------------------------------------------------- 掛在逐句輸出上


class _OkEngine:
    def generate_audio(self, text, file_name_no_ext=None):
        return "x.wav"

    async def async_generate_audio(self, text, file_name_no_ext=None):
        return "x.wav"

    def remove_file(self, filepath, verbose=True):
        pass


def _fake_prepare_audio_payload(audio_path, **kwargs):
    kwargs["audio_path"] = None
    payload = prepare_audio_payload(**kwargs)
    payload["audio"] = f"AUDIO:{audio_path}" if audio_path else None
    return payload


class _Send:
    def __init__(self):
        self.messages = []

    async def __call__(self, data):
        self.messages.append(json.loads(data))


class _Sentences:
    def __init__(self, pairs):
        self._pairs = pairs

    async def __aiter__(self):
        for display, tts in self._pairs:
            yield DisplayText(text=display), tts, Actions()


class _Translator:
    target_lang = "ja"

    def translate(self, text):
        return {"今天好嗎？": "今日は元気？", "再見。": "またね。"}.get(text, text)


PAIRS = [
    ("今天好嗎？", "今天好嗎？"),
    ("こんにちは", "こんにちは"),  # 同語言：沒翻譯，不審
    ("peko！", "peko！"),  # 只有口頭禪：照設定換掉，不審
    ("再見。", "再見。"),
]


def _pipeline(monkeypatch, auditor, *, after=None):
    """照正式流程：handle_sentence_output 每句呼叫一次，一輪結束跑 after。"""
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )

    async def run():
        manager = TTSTaskManager()
        send = _Send()
        kwargs = {} if auditor is None else {"translation_auditor": auditor}
        for pair in PAIRS:
            await handle_sentence_output(
                _Sentences([pair]),
                live2d_model=None,
                tts_engine=_OkEngine(),
                websocket_send=send,
                tts_manager=manager,
                translate_engine=_Translator(),
                voice_lang="ja",
                catchphrases={"peko": "ぺこ"},
                **kwargs,
            )
        await asyncio.gather(*manager.task_list)
        await manager._payload_queue.join()
        await audit.wait_background()
        if after is not None:
            after()
            await audit.wait_background()
        return send.messages

    return asyncio.run(run())


def test_one_batched_call_after_the_turn_not_per_sentence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audit.reset()
    character = _character()
    auditor = audit.auditor_for(character)
    client = FakeClient(_ok(2))
    auditor.client = client
    seen_during_turn = []

    def end_of_turn():
        seen_during_turn.append(len(client.calls))
        audit.flush_for(character)

    _pipeline(monkeypatch, auditor, after=end_of_turn)
    assert seen_during_turn == [0]  # 講話途中一次都沒問
    assert len(client.calls) == 1
    log = tmp_path / "chat_history" / "pekora" / "translation_audit" / "audit.jsonl"
    lines = [json.loads(line) for line in log.read_text("utf-8").splitlines()]
    assert [(line["original"], line["translated"]) for line in lines] == [
        ("今天好嗎？", "今日は元気？"),
        ("再見。", "またね。"),
    ]
    audit.reset()


def test_flush_for_does_nothing_when_switched_off_or_never_used(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audit.reset()

    async def run():
        audit.flush_for(_character(enabled=False))
        audit.flush_for(_character(uid="nobody"))
        audit.flush_for(None)
        await audit.wait_background()

    asyncio.run(run())
    assert not (tmp_path / "chat_history").exists()


def test_switched_off_the_payloads_are_the_same(tmp_path, monkeypatch):
    off = _pipeline(monkeypatch, None)
    on = _pipeline(monkeypatch, _auditor(tmp_path, FakeClient(_ok(2))))
    assert off == on


def test_process_agent_output_passes_the_characters_auditor(monkeypatch):
    seen = {}

    async def _fake_handle(*args, **kwargs):
        seen.update(kwargs)
        return ""

    from src.open_llm_vtuber.conversations import conversation_utils

    monkeypatch.setattr(conversation_utils, "handle_sentence_output", _fake_handle)

    class _Output:
        display_text = DisplayText(text="")

    monkeypatch.setattr(conversation_utils, "SentenceOutput", _Output)
    sentinel = object()
    monkeypatch.setattr(
        conversation_utils,
        "translation_auditor",
        lambda character: sentinel if character.translation_audit else None,
    )
    for flag, expected in ((True, sentinel), (False, None)):
        character = SimpleNamespace(
            character_name="佩克拉",
            conf_name="佩克拉",
            avatar="",
            catchphrases={},
            translation_audit=flag,
        )
        asyncio.run(
            process_agent_output(
                _Output(),
                character_config=character,
                live2d_model=None,
                tts_engine=None,
                websocket_send=None,
                tts_manager=None,
            )
        )
        assert seen["translation_auditor"] is expected


# ---------------------------------------------------------------- 實測後補的


def test_parse_ignores_what_follows_the_json():
    """9B 模型有時把整段 JSON 重複一次、尾巴多一個反引號。"""
    one = '{"results": [{"i": 1, "ok": true, "issues": []}]}'
    (result,) = parse_reply(one + ", " + one[1:] + "`", 1)
    assert result["ok"] is True
    (result,) = parse_reply("Here you go:\n" + one, 1)
    assert result["ok"] is True


@pytest.mark.parametrize(
    "original, translated, target",
    [
        ("安安。", "安安。", "ja"),  # 沒翻
        ("懂了嗎?", "理解了吗？", "ja"),  # 還是中文
        (
            "既然你不想學那些讓人頭痛的日語,那我們聊點輕鬆的?",
            "Since you don't want to learn Japanese, shall we talk?",
            "ja",
        ),  # 整句英文
    ],
)
def test_lines_plainly_not_in_the_target_language_are_flagged_without_the_model(
    original, translated, target
):
    (issue,) = audit.plain_issues(original, translated, target)
    assert issue["kind"] == "wrong_language"


@pytest.mark.parametrize(
    "original, translated, target",
    [
        ("沒事吧?", "大丈夫？", "ja"),  # 短的全漢字日文
        ("知道了。", "了解。", "ja"),
        (
            "是想說「kommen」還是「kommenen」?",
            "「kommen」なのか「kommenen」なのか？",
            "ja",
        ),
        ("Asia/Taipei 00:14", "台北 00:14", "ja"),
        ("你好", "こんにちは", "ja"),
        ("こんにちは", "你好", "zh"),
    ],
)
def test_plain_check_leaves_real_translations_alone(original, translated, target):
    assert audit.plain_issues(original, translated, target) == []


def test_plain_issues_are_recorded_even_when_the_model_says_ok(tmp_path):
    auditor = _auditor(tmp_path, FakeClient(_ok(1)))

    async def run():
        auditor.submit("懂了嗎?", "理解了吗？", "ja")
        await auditor.flush()

    asyncio.run(run())
    (line,) = _lines(tmp_path)
    assert [issue["kind"] for issue in line["issues"]] == ["wrong_language"]


def test_suggestions_need_an_issue_of_their_kind(tmp_path):
    """模型說句子沒問題、或只報了別種問題時，順手給的建議不算。"""
    reply = json.dumps(
        {
            "results": [
                {
                    "ok": False,
                    "issues": [{"kind": "name", "detail": "x"}],
                    "suggest": {
                        "protected_names": {"ペコラ": "ぺこら"},
                        "catchphrases": {"哈哈哈": "ハハハ"},
                    },
                }
            ]
        }
    )
    auditor = _auditor(tmp_path, FakeClient(reply))

    async def run():
        auditor.submit("哈哈哈佩克拉", "哈哈哈ペコラ", "ja")
        await auditor.flush()

    asyncio.run(run())
    (line,) = _lines(tmp_path)
    assert line["suggest"] == {
        "protected_names": {"ペコラ": "ぺこら"},
        "catchphrases": {},
    }


def test_foreign_words_copied_from_the_source_are_not_wrong_language(tmp_path):
    """她教對方念的外語詞照抄是對的；模型常把它標成 wrong_language。"""
    flagged = json.dumps(
        {
            "results": [
                {"ok": False, "issues": [{"kind": "wrong_language", "detail": "x"}]},
                {"ok": False, "issues": [{"kind": "wrong_language", "detail": "x"}]},
            ]
        }
    )
    auditor = _auditor(tmp_path, FakeClient(flagged))

    async def run():
        auditor.submit("哈哈哈,「The」?", "ハハハ、「The」？", "ja")
        auditor.submit("你那邊現在是凌晨喔?", "君の那边は夜明け前だ？", "ja")
        await auditor.flush()

    asyncio.run(run())
    copied, drifted = _lines(tmp_path)
    assert copied["issues"] == []
    assert [issue["kind"] for issue in drifted["issues"]] == ["wrong_language"]


# ---------------------------------------------------------------- 一輪結束才審


class _Engine:
    """agent.chat：兩句，記下每一句被取走時已經 flush 幾次。"""

    def __init__(self, events):
        self.events = events

    async def chat(self, batch_input):
        from src.open_llm_vtuber.agent.output_types import SentenceOutput

        for text in ("今天好嗎？", "再見。"):
            self.events.append("sentence")
            yield SentenceOutput(
                display_text=DisplayText(text=text), tts_text=text, actions=Actions()
            )


def _record_flushes(monkeypatch, events):
    monkeypatch.setattr(
        audit, "flush_for", lambda character: events.append(("flush", character))
    )


def test_a_single_conversation_turn_flushes_once_after_the_stream(monkeypatch):
    from src.open_llm_vtuber.conversations import single_conversation

    events = []
    _record_flushes(monkeypatch, events)

    async def nothing(*_args, **_kwargs):
        return None

    async def spoken(output_item, **_kwargs):
        return output_item.display_text.text

    async def typed(user_input, *_args, **_kwargs):
        return user_input

    monkeypatch.setattr(single_conversation, "process_user_input", typed)
    monkeypatch.setattr(single_conversation, "send_conversation_start_signals", nothing)
    monkeypatch.setattr(single_conversation, "create_batch_input", lambda **kw: None)
    monkeypatch.setattr(single_conversation, "_speak", spoken)
    monkeypatch.setattr(single_conversation, "finalize_conversation_turn", nothing)
    monkeypatch.setattr(single_conversation, "send_character_mood", nothing)
    monkeypatch.setattr(single_conversation, "cleanup_conversation", lambda *a: None)
    character = SimpleNamespace(
        human_name="me", character_name="佩克拉", conf_uid="pekora", reply_language=""
    )
    context = SimpleNamespace(
        agent_engine=_Engine(events),
        asr_engine=None,
        history_uid="",
        character_config=character,
        system_config=None,
    )
    reply = asyncio.run(
        single_conversation.process_single_conversation(
            context, nothing, "client", "你好"
        )
    )
    assert reply == "今天好嗎？再見。"
    assert events == ["sentence", "sentence", ("flush", character)]


def test_a_group_member_turn_flushes_once_after_the_stream(monkeypatch):
    from src.open_llm_vtuber.conversations import group_conversation

    events = []
    _record_flushes(monkeypatch, events)

    async def spoken(output, **_kwargs):
        return output.display_text.text

    monkeypatch.setattr(group_conversation, "process_agent_output", spoken)
    character = SimpleNamespace(character_name="佩克拉", conf_uid="pekora")
    context = SimpleNamespace(
        agent_engine=_Engine(events),
        character_config=character,
        live2d_model=None,
        tts_engine=None,
        translate_engine=None,
        subtitle_translate_engine=None,
    )
    reply = asyncio.run(
        group_conversation.process_member_response(context, None, None, None)
    )
    assert reply == "今天好嗎？再見。"
    assert events == ["sentence", "sentence", ("flush", character)]


# ---------------------------------------------------------------- 存檔上限與壞檔


def _entry(n):
    return {
        "time": "t",
        "original": f"句{n}",
        "translated": "x",
        "target_lang": "ja",
        "issues": [],
        "suggest": {},
    }


def test_the_log_keeps_the_last_lines_when_too_long(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "MAX_LOG_LINES", 5)
    store = AuditStore(tmp_path / "audit")
    for n in range(4):
        store.record([_entry(n)])
    assert len(_lines(tmp_path)) == 4
    store.record([_entry(n) for n in range(4, 9)])
    assert [line["original"] for line in _lines(tmp_path)] == [
        f"句{n}" for n in range(4, 9)
    ]
    assert not list((tmp_path / "audit").glob(".*.tmp"))
    assert _summary(tmp_path)["audited"] == 9


def test_the_log_keeps_the_last_lines_when_too_big(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "MAX_LOG_BYTES", 300)
    monkeypatch.setattr(audit, "MAX_LOG_LINES", 3)
    store = AuditStore(tmp_path / "audit")
    store.record([_entry(n) for n in range(3)])
    assert len(_lines(tmp_path)) == 3  # 剛好上限，沒超過大小
    store.record([_entry(3)])
    assert [line["original"] for line in _lines(tmp_path)] == ["句1", "句2", "句3"]


def test_default_log_cap():
    assert audit.MAX_LOG_LINES == 2000
    assert audit.MAX_LOG_BYTES == 1_000_000


def test_summary_fields_of_the_wrong_type_are_reset(tmp_path):
    directory = tmp_path / "audit"
    directory.mkdir()
    (directory / "summary.json").write_text(
        json.dumps(
            {
                "audited": "many",
                "flagged": True,
                "protected_names": [],
                "catchphrases": {"peko": {"ぺこ": 2}},
                "suspicious": {},
            }
        ),
        "utf-8",
    )
    summary = audit.load_summary(directory)
    assert summary["audited"] == 0
    assert summary["flagged"] == 0
    assert summary["protected_names"] == {}
    assert summary["catchphrases"] == {"peko": {"ぺこ": 2}}
    assert summary["suspicious"] == []
    AuditStore(directory).record([_entry(0)])  # 不炸
    assert audit.load_summary(directory)["audited"] == 1


def test_a_failed_background_task_is_logged(monkeypatch):
    warnings = []
    monkeypatch.setattr(audit.logger, "warning", warnings.append)

    async def boom():
        raise RuntimeError("disk full")

    async def run():
        audit.spawn(boom())
        await audit.wait_background()
        await asyncio.sleep(0)

    asyncio.run(run())
    assert any("disk full" in w for w in warnings)
