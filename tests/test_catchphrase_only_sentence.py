"""只有口頭禪的句子不經翻譯模型：語音換成角色設定的寫法，字幕原樣。

實際發生過：回覆語言是中文、語音是日文、字幕是中文的角色說「konpeko！」，
字幕翻譯器把它翻成「孔佩可！」，語音翻譯器有時寫成「コンペコ」、有時留下
拉丁字母讓日文語音亂念。整句只有口頭禪時，答案是確定的，不必問模型。
"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.conversations import conversation_utils
from src.open_llm_vtuber.conversations.conversation_utils import (
    handle_sentence_output,
    process_agent_output,
)

PEKO = {"peko": "ぺこ", "konpeko": "こんぺこ", "otsupeko": "おつぺこ"}


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


def _run(texts, catchphrases, voice_lang="ja"):
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
            voice_lang=voice_lang,
            catchphrases=catchphrases,
        )
    )
    return full, tts_manager.spoken, audio, subtitle


def test_a_catchphrase_only_sentence_skips_both_translators():
    full, spoken, audio, subtitle = _run(["konpeko！"], PEKO)

    assert spoken == [("こんぺこ！", "konpeko！")]
    assert audio.calls == []
    assert subtitle.calls == []
    # 正典文字（記憶、紀錄用的）不動。
    assert full == "konpeko！"


def test_several_catchphrases_in_one_sentence_are_all_replaced():
    _, spoken, audio, subtitle = _run(["Konpeko, peko!"], PEKO)

    assert spoken == [("こんぺこ, ぺこ!", "Konpeko, peko!")]
    assert audio.calls == subtitle.calls == []


def test_a_mixed_sentence_still_goes_through_both_translators():
    sentence = "要叫「konpeko」才是打招呼的方式!"
    _, spoken, audio, subtitle = _run([sentence], PEKO)

    assert audio.calls == [sentence]
    # 中文句子、中文字幕：字幕語言相同，照舊不翻。這裡只要確認音訊照樣送模型。
    assert spoken == [(f"[日文]{sentence}", sentence)]


def test_a_mixed_latin_sentence_still_calls_the_subtitle_translator():
    _, spoken, audio, subtitle = _run(["konpeko everyone!"], PEKO)

    assert audio.calls == ["konpeko everyone!"]
    assert subtitle.calls == ["konpeko everyone!"]


def test_without_catchphrases_the_sentence_is_translated_as_before():
    _, spoken, audio, subtitle = _run(["konpeko！"], {})

    assert audio.calls == ["konpeko！"]
    assert subtitle.calls == ["konpeko！"]


def test_audio_keeps_the_sentence_when_the_voice_speaks_its_language():
    """語音語言跟這句一樣時本來就不翻；口頭禪的目標寫法是給語音語言的，也不換。"""
    _, spoken, audio, subtitle = _run(["konpeko！"], PEKO, voice_lang="en")

    assert spoken == [("konpeko！", "konpeko！")]
    assert audio.calls == subtitle.calls == []


def test_process_agent_output_passes_the_current_characters_catchphrases(
    monkeypatch,
):
    captured = {}

    async def _fake_handle(*args, **kwargs):
        captured.update(kwargs)
        return ""

    monkeypatch.setattr(conversation_utils, "handle_sentence_output", _fake_handle)
    character = SimpleNamespace(
        character_name="Pekora",
        conf_name="pekora",
        avatar="",
        tts_config=None,
        catchphrases=PEKO,
    )
    output = conversation_utils.SentenceOutput(
        display_text=DisplayText(text="konpeko！"),
        tts_text="konpeko！",
        actions=Actions(),
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

    assert captured["catchphrases"] == PEKO
