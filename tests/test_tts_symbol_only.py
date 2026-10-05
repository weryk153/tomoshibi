"""只有符號的句子直接走靜音：不合成、不重試、不跳提示。

以前 speak() 的空字串判斷只拿掉幾個標點，「……」「♪」、表情符號、*動作* 這類
句子會送去引擎。GPT-SoVITS 對這種輸入回 400（→ None），加上重試之後就變成
多打一次服務、再跳一則「語音合成失敗」——其實這句本來就沒有東西可念。
"""

import asyncio
import json

import pytest

from src.open_llm_vtuber.agent.output_types import DisplayText
from src.open_llm_vtuber.conversations import tts_manager as tts_manager_module
from src.open_llm_vtuber.conversations.text_content import has_speakable_text
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


class _CountingEngine(TTSInterface):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate_audio(self, text, file_name_no_ext=None):  # pragma: no cover
        raise NotImplementedError

    async def async_generate_audio(self, text, file_name_no_ext=None):
        self.calls.append(text)
        return f"{text}.wav"

    def remove_file(self, filepath, verbose=True):
        pass


class _RecordingSend:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, data: str) -> None:
        self.messages.append(json.loads(data))


def _speak(text, monkeypatch):
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )
    engine = _CountingEngine()

    async def _run():
        manager = TTSTaskManager()
        send = _RecordingSend()
        await manager.speak(
            tts_text=text,
            display_text=DisplayText(text=text),
            actions=None,
            live2d_model=None,
            tts_engine=engine,
            websocket_send=send,
        )
        if manager.task_list:
            await asyncio.gather(*manager.task_list)
        await manager._payload_queue.join()
        return send.messages

    return engine.calls, asyncio.run(_run())


@pytest.mark.parametrize(
    "text", ["……", "♪", "😂", "*轉頭*", "～～", "...", "(*點頭*)", "  ！？ "]
)
def test_symbol_only_sentence_is_silent_without_synthesis_or_notice(text, monkeypatch):
    calls, messages = _speak(text, monkeypatch)

    assert calls == []
    assert [m["type"] for m in messages] == ["audio"]
    assert messages[0]["audio"] is None
    assert messages[0]["display_text"]["text"] == text  # 聊天泡泡照樣有這句


@pytest.mark.parametrize("text", ["哈哈哈！", "はい", "OK", "3", "*轉頭* 你好"])
def test_sentence_with_letters_or_digits_is_synthesized(text, monkeypatch):
    calls, messages = _speak(text, monkeypatch)

    assert calls == [text]
    assert messages[0]["audio"] == f"AUDIO:{text}.wav"


def test_has_speakable_text():
    assert not has_speakable_text("")
    assert not has_speakable_text("…♪😂")
    assert not has_speakable_text("*轉頭*")
    assert has_speakable_text("哈↗哈！")
    assert has_speakable_text("１２３")
