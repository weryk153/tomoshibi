"""只有笑聲的句子不換字幕。

斷句會把「哈↗哈↘哈↗！」切成獨立一句，畫面上就閃一行「哈哈哈！」。聲音照播，
但字幕留著上一句——後端在 payload 標 keep_subtitle，前端照著跳過。
規則是通用的，不靠每個角色設定。
"""

import asyncio
import json

import pytest

from src.open_llm_vtuber.agent.output_types import DisplayText
from src.open_llm_vtuber.conversations import tts_manager as tts_manager_module
from src.open_llm_vtuber.conversations.laughter import is_laughter_only
from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager
from src.open_llm_vtuber.tts.tts_interface import TTSInterface


@pytest.mark.parametrize(
    "text",
    [
        "哈↗哈↘哈↗！",
        "哈哈",
        "哈哈哈哈哈……",
        "呵呵。",
        "嘿嘿～",
        "嘻嘻嘻！",
        "哈哈哈、嘿嘿",
        "ははは",
        "あはははっ！",
        "ハハハ",
        "ﾊﾊﾊ",
        "ふふっ",
        "ふふふ…",
        "へへ",
        "えへへ♪",
        "www",
        "ｗｗｗ",
        "WWWW",
        "lol",
        "LOL!",
        "haha",
        "Hahaha!",
        "ahaha~",
        "hehe",
        "  (哈哈)  ",
        "「ふふ」",
    ],
)
def test_laughter_only(text):
    assert is_laughter_only(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "！？…",
        "哈",
        "は",
        "ハ",
        "w",
        "ha",
        "哈哈，你真好笑",
        "哈囉",
        "はい",
        "はは、そうだね",
        "ふふ、可愛い",
        "what",
        "wow",
        "hello",
        "lollipop",
        "我笑了",
        "笑",
        "123",
    ],
)
def test_not_laughter_only(text):
    assert not is_laughter_only(text)


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


class _OkEngine(TTSInterface):
    def generate_audio(self, text, file_name_no_ext=None):  # pragma: no cover
        raise NotImplementedError

    async def async_generate_audio(self, text, file_name_no_ext=None):
        return f"{text}.wav"

    def remove_file(self, filepath, verbose=True):
        pass


class _RecordingSend:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, data: str) -> None:
        self.messages.append(json.loads(data))


def _speak(items, monkeypatch):
    """items: (display, subtitle 或 None)。回傳送出的 payload。"""
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )

    async def _run():
        manager = TTSTaskManager()
        send = _RecordingSend()
        for display, subtitle in items:
            await manager.speak(
                tts_text=display,
                display_text=DisplayText(text=display),
                actions=None,
                live2d_model=None,
                tts_engine=_OkEngine(),
                websocket_send=send,
                subtitle_text=subtitle,
            )
        await asyncio.gather(*manager.task_list)
        await manager._payload_queue.join()
        return send.messages

    return asyncio.run(_run())


def test_laugh_payload_keeps_audio_and_chat_text_but_flags_the_subtitle(monkeypatch):
    first, laugh, last = _speak(
        [("你回來啦。", None), ("哈↗哈↘哈↗！", None), ("今天好嗎？", None)],
        monkeypatch,
    )

    assert laugh["keep_subtitle"] is True
    assert laugh["audio"] == "AUDIO:哈↗哈↘哈↗！.wav"  # 聲音照播
    assert laugh["display_text"]["text"] == "哈↗哈↘哈↗！"  # 對話紀錄照舊
    assert first["keep_subtitle"] is False
    assert last["keep_subtitle"] is False


def test_the_flag_follows_the_text_shown_on_screen(monkeypatch):
    """字幕翻譯後的文字才是畫面上那一行。"""
    (translated_laugh,) = _speak([("ははは！", "哈哈哈！")], monkeypatch)
    (translated_words,) = _speak([("ははは！", "哈哈，好啊")], monkeypatch)

    assert translated_laugh["keep_subtitle"] is True
    assert translated_words["keep_subtitle"] is False


def test_silent_payload_is_flagged_too(monkeypatch):
    """要念的文字濾完是空的會走靜音 payload；旗標照樣帶上，前端行為一致。"""
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )

    async def _run():
        manager = TTSTaskManager()
        send = _RecordingSend()
        for display in ("哈哈哈！", "嗯？"):
            await manager.speak(
                tts_text="...",
                display_text=DisplayText(text=display),
                actions=None,
                live2d_model=None,
                tts_engine=_OkEngine(),
                websocket_send=send,
            )
        await manager._payload_queue.join()
        return send.messages

    laugh, other = asyncio.run(_run())
    assert laugh["audio"] is None and other["audio"] is None
    assert laugh["keep_subtitle"] is True
    assert other["keep_subtitle"] is False
