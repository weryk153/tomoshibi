"""語音翻譯兩次都不是她的語言：那句靜音、字幕照顯示。

實際發生過：回覆中文、語音日文的角色，中→日翻譯偶爾整句用英文答，GPT-SoVITS
就用日文聲線唸英文。翻譯器重試後仍失敗會丟 ``UnspeakableTranslation``；這裡確認
對話串接把那句的語音文字清空（tts_manager 對空字串走靜音 payload），而正典文字、
字幕都不受影響。
"""

import asyncio

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


async def _noop_send(_data):
    return None


def _run(texts, unspeakable, bilingual=False):
    tts_manager = _TTSManager()
    full = asyncio.run(
        handle_sentence_output(
            _Sentences(texts),
            live2d_model=None,
            tts_engine=None,
            websocket_send=_noop_send,
            tts_manager=tts_manager,
            translate_engine=_AudioTranslator(unspeakable),
            subtitle_translate_engine=None,
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


def test_the_silent_payload_of_a_real_sentence_is_flagged_show_subtitle():
    """前端對靜音 payload 不換畫面字幕（「……」沒必要）；有字的句子要標起來。"""
    from src.open_llm_vtuber.conversations.tts_manager import _mark_silent_sentence

    sentence = {}
    _mark_silent_sentence(sentence, DisplayText(text="那我們聊點輕鬆的？"), None)
    assert sentence == {"show_subtitle": True}

    translated = {}
    _mark_silent_sentence(translated, DisplayText(text="……"), "那我們聊點輕鬆的？")
    assert translated == {"show_subtitle": True}

    dots = {}
    _mark_silent_sentence(dots, DisplayText(text="……"), None)
    assert dots == {}
