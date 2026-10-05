"""語音合成失敗要重試一次，再失敗就讓使用者看得到。

GPT-SoVITS 在記憶體吃緊時偶爾會超過 120 秒，以前那句就變成只有字幕、
聲音悄悄不見。重試放在 TTSTaskManager（跟引擎無關），所以每個 TTS 後端都有。

假引擎照劇本回應，不碰真的服務；prepare_audio_payload 換成不跑 ffmpeg 的替身。
"""

import asyncio
import json

import pytest
import requests

from src.open_llm_vtuber.agent.output_types import DisplayText
from src.open_llm_vtuber.conversations import tts_manager as tts_manager_module
from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager
from src.open_llm_vtuber.tts.tts_interface import TTSInterface


def _fake_prepare_audio_payload(
    audio_path, display_text=None, actions=None, subtitle_text=None, **_
):
    if isinstance(display_text, DisplayText):
        display_text = display_text.to_dict()
    return {
        "type": "audio",
        "audio": f"AUDIO:{audio_path}" if audio_path else None,
        "display_text": display_text,
        "subtitle_text": subtitle_text,
        "actions": None,
    }


@pytest.fixture(autouse=True)
def _no_ffmpeg(monkeypatch):
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )


class _ScriptedTTSEngine(TTSInterface):
    """每句話照劇本依序回應：'ok' 回檔名、'none' 回 None、例外就丟出去。"""

    def __init__(self, script: dict[str, list]) -> None:
        self.script = {text: list(steps) for text, steps in script.items()}
        self.calls: list[str] = []

    def generate_audio(self, text, file_name_no_ext=None):  # pragma: no cover
        raise NotImplementedError

    async def async_generate_audio(self, text, file_name_no_ext=None):
        self.calls.append(text)
        steps = self.script.get(text) or ["ok"]
        step = steps.pop(0) if len(steps) > 1 else steps[0]
        await asyncio.sleep(0)
        if isinstance(step, BaseException):
            raise step
        if step == "none":
            return None
        return f"{text}.wav"

    def remove_file(self, filepath, verbose=True):
        pass


class _RecordingSend:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, data: str) -> None:
        self.messages.append(json.loads(data))


async def _speak_all(texts, engine):
    manager = TTSTaskManager()
    send = _RecordingSend()
    for text in texts:
        await manager.speak(
            tts_text=text,
            display_text=DisplayText(text=text),
            actions=None,
            live2d_model=None,
            tts_engine=engine,
            websocket_send=send,
        )
    await asyncio.gather(*manager.task_list)
    await manager._payload_queue.join()
    return send.messages


def _errors(messages):
    return [m for m in messages if m["type"] == "error"]


def test_success_first_time_does_not_retry():
    engine = _ScriptedTTSEngine({"hello": ["ok"]})
    messages = asyncio.run(_speak_all(["hello"], engine))

    assert engine.calls == ["hello"]
    assert messages[0]["audio"] == "AUDIO:hello.wav"
    assert _errors(messages) == []


def test_one_failure_then_success_sends_audio_without_error():
    engine = _ScriptedTTSEngine({"hello": [requests.exceptions.ReadTimeout(), "ok"]})
    messages = asyncio.run(_speak_all(["hello"], engine))

    assert engine.calls == ["hello", "hello"]
    assert [m["type"] for m in messages] == ["audio"]
    assert messages[0]["audio"] == "AUDIO:hello.wav"


def test_none_then_success_also_retries():
    engine = _ScriptedTTSEngine({"hello": ["none", "ok"]})
    messages = asyncio.run(_speak_all(["hello"], engine))

    assert engine.calls == ["hello", "hello"]
    assert messages[0]["audio"] == "AUDIO:hello.wav"
    assert _errors(messages) == []


def test_two_failures_send_silent_payload_and_a_visible_error():
    engine = _ScriptedTTSEngine({"hello": [requests.exceptions.ReadTimeout()]})
    messages = asyncio.run(_speak_all(["hello"], engine))

    assert engine.calls == ["hello", "hello"]
    audio, error = messages
    assert audio["type"] == "audio"
    assert audio["audio"] is None
    assert (
        audio["display_text"]["text"] == "hello"
    )  # 聊天泡泡照樣有這句（靜音 payload 不換畫面字幕）
    assert error["type"] == "error"
    assert error["text_key"] == "notification.ttsTimedOut"
    assert "逾時" in error["message"]


def test_failure_that_is_not_a_timeout_uses_the_generic_message():
    engine = _ScriptedTTSEngine({"hello": ["none"]})
    messages = asyncio.run(_speak_all(["hello"], engine))

    assert engine.calls == ["hello", "hello"]
    (error,) = _errors(messages)
    assert error["text_key"] == "notification.ttsFailed"
    assert "逾時" not in error["message"]


def test_a_failed_sentence_keeps_its_place_in_the_order():
    engine = _ScriptedTTSEngine(
        {"one": ["ok"], "two": [RuntimeError("boom")], "three": ["ok"]}
    )
    messages = asyncio.run(_speak_all(["one", "two", "three"], engine))

    assert [
        (m["type"], (m.get("display_text") or {}).get("text")) for m in messages
    ] == [
        ("audio", "one"),
        ("audio", "two"),
        ("error", None),
        ("audio", "three"),
    ]
    assert messages[1]["audio"] is None
    assert messages[3]["audio"] == "AUDIO:three.wav"


def test_cancelled_synthesis_is_not_retried():
    """clear() 取消進行中的合成時不能被當成失敗重試、也不能跳錯誤通知。"""

    async def _run():
        started = asyncio.Event()
        calls = []

        class _Hanging(_ScriptedTTSEngine):
            async def async_generate_audio(self, text, file_name_no_ext=None):
                calls.append(text)
                started.set()
                await asyncio.sleep(10)

        manager = TTSTaskManager()
        send = _RecordingSend()
        await manager.speak(
            tts_text="hello",
            display_text=DisplayText(text="hello"),
            actions=None,
            live2d_model=None,
            tts_engine=_Hanging({}),
            websocket_send=send,
        )
        task = manager.task_list[0]
        await started.wait()
        manager.clear()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        return calls, send.messages

    calls, messages = asyncio.run(_run())
    assert calls == ["hello"]
    assert messages == []
