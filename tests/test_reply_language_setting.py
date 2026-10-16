"""角色設了回覆語言，就照設定決定翻不翻，不逐句猜。

實際發生過：三月七的回覆語言是中文，她說「我是三月なのか，剛才聽到你的聲音傳過來，」。
句子裡有假名，逐句判斷把它當成日文：字幕被「日翻中」成「我是不是三月啊？」，
語音則沒翻、把中文混假名直接丟給日文語音唸。
"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.conversations import conversation_utils
from src.open_llm_vtuber.conversations.conversation_utils import (
    handle_sentence_output,
    process_agent_output,
)

SAID = "我是三月なのか，剛才聽到你的聲音傳過來，"


class _Sentences:
    def __init__(self, texts):
        self._texts = texts

    async def __aiter__(self):
        for text in self._texts:
            yield DisplayText(text=text), text, Actions()


class _Translator:
    def __init__(self, target_lang):
        self.target_lang = target_lang
        self.calls = []

    def translate(self, text):
        self.calls.append(text)
        return f"[{self.target_lang}]{text}"


class _TTSManager:
    def __init__(self):
        self.spoken = []

    async def speak(self, **kwargs):
        self.spoken.append((kwargs["tts_text"], kwargs["subtitle_text"]))


async def _noop_send(_data):
    return None


def _run(texts, **kwargs):
    audio = _Translator("日文")
    subtitle = _Translator("繁體中文")
    tts_manager = _TTSManager()
    full = asyncio.run(
        handle_sentence_output(
            _Sentences(texts),
            live2d_model=None,
            tts_engine=None,
            websocket_send=_noop_send,
            tts_manager=tts_manager,
            translate_engine=audio,
            subtitle_translate_engine=subtitle,
            voice_lang="ja",
            **kwargs,
        )
    )
    return full, tts_manager.spoken, audio, subtitle


def test_a_chinese_reply_with_a_kana_name_is_still_chinese():
    full, spoken, audio, subtitle = _run([SAID], reply_lang="zh")

    assert audio.calls == [SAID]
    assert subtitle.calls == []
    assert spoken == [(f"[日文]{SAID}", SAID)]
    assert full == SAID


def test_without_a_setting_each_sentence_is_still_detected():
    _, _, audio, subtitle = _run(["こんにちは"])

    assert audio.calls == []
    assert subtitle.calls == ["こんにちは"]


def test_process_agent_output_passes_the_characters_reply_language(monkeypatch):
    captured = {}

    async def _fake_handle(*args, **kwargs):
        captured.update(kwargs)
        return ""

    monkeypatch.setattr(conversation_utils, "handle_sentence_output", _fake_handle)

    def run(reply_language):
        character = SimpleNamespace(
            character_name="三月なのか",
            conf_name="march_7th",
            avatar="",
            tts_config=None,
            reply_language=reply_language,
        )
        output = conversation_utils.SentenceOutput(
            display_text=DisplayText(text=SAID), tts_text=SAID, actions=Actions()
        )
        asyncio.run(
            process_agent_output(
                output,
                character_config=character,
                live2d_model=None,
                tts_engine=None,
                websocket_send=_noop_send,
                tts_manager=None,
            )
        )
        return captured["reply_lang"]

    assert run("Traditional Chinese (Taiwan)") == "zh"
    assert run("Japanese") == "ja"
    assert run("") is None
