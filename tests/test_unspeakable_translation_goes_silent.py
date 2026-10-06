"""語音翻譯兩次都不是她的語言：那句靜音、字幕照顯示。

實際發生過：回覆中文、語音日文的角色，中→日翻譯偶爾整句用英文答，GPT-SoVITS
就用日文聲線唸英文。翻譯器重試後仍失敗會丟 ``UnspeakableTranslation``；這裡確認
對話串接把那句的語音文字清空（tts_manager 對空字串走靜音 payload），而正典文字、
字幕都不受影響。
"""

import asyncio
import json

from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.conversations.conversation_utils import (
    handle_sentence_output,
)
from src.open_llm_vtuber.translate.translate_interface import UnspeakableTranslation


class _Sentences:
    def __init__(self, texts):
        self._texts = texts

    async def __aiter__(self):
        for text in self._texts:
            yield DisplayText(text=text), text, Actions()


class _AudioTranslator:
    target_lang = "日文"

    def __init__(self, unspeakable):
        self.unspeakable = set(unspeakable)

    def translate(self, text):
        if text in self.unspeakable:
            raise UnspeakableTranslation(text)
        return f"[日文]{text}"


class _TTSManager:
    def __init__(self):
        self.spoken = []

    async def speak(self, **kwargs):
        self.spoken.append(
            (kwargs["tts_text"], kwargs["subtitle_text"], kwargs.get("spoken_text"))
        )
        self.kwargs = kwargs


async def _noop_send(_data):
    return None


class _SubtitleTranslator:
    target_lang = "日文"

    def __init__(self, unspeakable):
        self.unspeakable = set(unspeakable)

    def translate(self, text):
        if text in self.unspeakable:
            raise UnspeakableTranslation(text)
        return f"[字幕]{text}"


class _SilentTTSManager:
    """只記每句送出的 kwargs；靜音與否交給真的 TTSTaskManager 另外測。"""

    def __init__(self):
        self.calls = []

    async def speak(self, **kwargs):
        self.calls.append(kwargs)


def _run(texts, unspeakable, bilingual=False, subtitle_unspeakable=None):
    tts_manager = _TTSManager()
    full = asyncio.run(
        handle_sentence_output(
            _Sentences(texts),
            live2d_model=None,
            tts_engine=None,
            websocket_send=_noop_send,
            tts_manager=tts_manager,
            translate_engine=_AudioTranslator(unspeakable),
            subtitle_translate_engine=(
                _SubtitleTranslator(subtitle_unspeakable)
                if subtitle_unspeakable is not None
                else None
            ),
            voice_lang="ja",
            bilingual_subtitle=bilingual,
        )
    )
    return full, tts_manager.spoken


def test_an_unspeakable_sentence_is_spoken_as_nothing_and_subtitled_as_usual():
    full, spoken = _run(["那我們聊點輕鬆的？", "好啊！"], {"那我們聊點輕鬆的？"})

    assert spoken == [
        ("", "那我們聊點輕鬆的？", None),
        ("[日文]好啊！", "好啊！", None),
    ]
    # 正典文字（記憶、紀錄用的）不動。
    assert full == "那我們聊點輕鬆的？好啊！"


def test_bilingual_subtitle_shows_no_spoken_line_for_an_unspeakable_sentence():
    _, spoken = _run(["那我們聊點輕鬆的？"], {"那我們聊點輕鬆的？"}, bilingual=True)

    assert spoken == [("", "那我們聊點輕鬆的？", None)]


def test_the_silenced_sentence_is_marked_so_the_subtitle_still_changes():
    """靜音 payload 的畫面字幕本來不動；這種句子要帶 silenced 讓 tts_manager 標
    show_subtitle。有聲的句子不帶。"""
    tts_manager = _SilentTTSManager()
    asyncio.run(
        handle_sentence_output(
            _Sentences(["那我們聊點輕鬆的？", "好啊！"]),
            live2d_model=None,
            tts_engine=None,
            websocket_send=_noop_send,
            tts_manager=tts_manager,
            translate_engine=_AudioTranslator({"那我們聊點輕鬆的？"}),
            subtitle_translate_engine=None,
            voice_lang="ja",
        )
    )
    silenced, spoken = tts_manager.calls
    assert silenced["tts_text"] == "" and silenced["silenced"] is True
    assert "silenced" not in spoken


def test_a_subtitle_that_cannot_be_translated_shows_the_reply_and_goes_on():
    """玩家語言選日文時字幕翻譯器的目標也是日文：翻不出來就顯示原文，後面的句子
    照常，正典文字完整——不能讓整段回覆因此中斷。"""
    full, spoken = _run(
        ["那我們聊點輕鬆的？", "好啊！"],
        unspeakable=set(),
        subtitle_unspeakable={"那我們聊點輕鬆的？"},
    )

    assert spoken == [
        ("[日文]那我們聊點輕鬆的？", "那我們聊點輕鬆的？", None),
        ("[日文]好啊！", "[字幕]好啊！", None),
    ]
    assert full == "那我們聊點輕鬆的？好啊！"


def _payload_for(display, tts_text, **speak_kwargs):
    """走真的 TTSTaskManager，拿它送到前端的那個 payload。"""
    from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager

    sent = []

    async def send(data):
        sent.append(data)

    async def run():
        manager = TTSTaskManager()
        await manager.speak(
            tts_text=tts_text,
            display_text=DisplayText(text=display),
            actions=None,
            live2d_model=None,
            tts_engine=None,
            websocket_send=send,
            **speak_kwargs,
        )
        await manager._payload_queue.join()

    asyncio.run(run())
    return json.loads(sent[0]) if isinstance(sent[0], str) else sent[0]


def test_only_the_silenced_sentence_gets_show_subtitle():
    """「（笑）」「……」這種本來就沒話念的句子，靜音 payload 跟以前一樣不帶旗標。"""
    assert (
        _payload_for("那我們聊點輕鬆的？", "", silenced=True)["show_subtitle"] is True
    )
    assert "show_subtitle" not in _payload_for("（笑）", "")
    assert "show_subtitle" not in _payload_for("……", "")
