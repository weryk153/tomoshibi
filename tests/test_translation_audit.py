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


def test_batches_every_four_lines(tmp_path):
    client = FakeClient(_ok(4))
    auditor = _auditor(tmp_path, client)

    async def run():
        for n in range(3):
            await auditor.submit(f"句{n}", f"文{n}", "ja")
        assert client.calls == []
        await auditor.submit("句3", "文3", "ja")

    asyncio.run(run())
    assert len(client.calls) == 1
    prompt = client.calls[0][-1]["content"]
    assert all(f"句{n}" in prompt and f"文{n}" in prompt for n in range(4))
    assert [line["original"] for line in _lines(tmp_path)] == [
        "句0",
        "句1",
        "句2",
        "句3",
    ]


def test_flush_sends_what_is_left(tmp_path):
    client = FakeClient(_ok(2))
    auditor = _auditor(tmp_path, client)

    async def run():
        await auditor.submit("句0", "文0", "ja")
        await auditor.submit("句1", "文1", "ja")
        await auditor.flush()
        await auditor.flush()  # 空的佇列不呼叫

    asyncio.run(run())
    assert len(client.calls) == 1
    assert len(_lines(tmp_path)) == 2


def test_queue_keeps_the_newest_eight(tmp_path):
    """模型還在審上一批時進來的句子排隊；超過上限丟最舊的。"""
    client = FakeClient(_ok(4), delay=0.05)
    auditor = _auditor(tmp_path, client)

    async def run():
        first = [
            asyncio.create_task(auditor.submit(f"前{n}", f"x{n}", "ja"))
            for n in range(4)
        ]
        await asyncio.sleep(0.01)  # 第一批已經送出去，模型還沒回
        assert len(client.calls) == 1
        late = [
            asyncio.create_task(auditor.submit(f"後{n}", f"y{n}", "ja"))
            for n in range(12)
        ]
        await asyncio.gather(*first, *late)
        await auditor.flush()

    asyncio.run(run())
    originals = [line["original"] for line in _lines(tmp_path)]
    assert originals[:4] == [f"前{n}" for n in range(4)]
    assert originals[4:] == [f"後{n}" for n in range(4, 12)]


def test_submit_drops_the_oldest_when_full(tmp_path):
    client = FakeClient(_ok(4))
    auditor = _auditor(tmp_path, client, batch_size=100)

    async def run():
        for n in range(10):
            await auditor.submit(f"句{n}", f"文{n}", "ja")

    asyncio.run(run())
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
        await auditor.submit("句", "文", "ja")
        await auditor.flush()

    asyncio.run(run())
    assert _lines(tmp_path) == []
    assert len(auditor._queue) == 0


def test_timeout_is_dropped_quietly(tmp_path):
    client = FakeClient(_ok(1), delay=1.0)
    auditor = _auditor(tmp_path, client, timeout=0.01)

    async def run():
        await auditor.submit("句", "文", "ja")
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
                    "issues": [{"kind": "name", "detail": "ぺこら written as ペコラ"}],
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
            await auditor.submit("佩克拉今天也很好peko", "ペコラは今日も元気", "ja")
            await auditor.submit("你好", "こんにちは", "ja")
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
        await auditor.submit("今天天氣很好", "今日はいい天気", "ja")
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
        await auditor.submit("句", "文", "ja")
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


def _pipeline(monkeypatch, auditor):
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )

    async def run():
        manager = TTSTaskManager()
        send = _Send()
        kwargs = {} if auditor is None else {"translation_auditor": auditor}
        await handle_sentence_output(
            _Sentences(PAIRS),
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
        return send.messages

    return asyncio.run(run())


def test_translated_lines_are_audited_and_flushed_at_the_end(tmp_path, monkeypatch):
    client = FakeClient(_ok(2))
    auditor = _auditor(tmp_path, client)
    _pipeline(monkeypatch, auditor)
    assert len(client.calls) == 1  # 兩句沒到門檻，回覆結束時 flush
    assert [(line["original"], line["translated"]) for line in _lines(tmp_path)] == [
        ("今天好嗎？", "今日は元気？"),
        ("再見。", "またね。"),
    ]


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
