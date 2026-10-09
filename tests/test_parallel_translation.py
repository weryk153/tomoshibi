"""句子一出來就同時送去翻譯，交給語音合成時照原本的順序。

worker 的 LM Studio 一顆 9B 同時接 4 個請求。以前一句翻完才翻下一句，而且
第二句要等第一句翻完才送出，句子之間一直在排隊。
"""

import asyncio
import threading
import time

from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.conversations.conversation_utils import (
    SentenceOutput,
    handle_sentence_output,
)


class SlowTranslator:
    def __init__(self):
        self.started = {}
        self.finished = {}
        self.lock = threading.Lock()

    def translate(self, text):
        with self.lock:
            self.started[text] = time.monotonic()
        time.sleep(0.4 if text.startswith("第一") else 0.1)
        with self.lock:
            self.finished[text] = time.monotonic()
        return "訳:" + text


class Speaker:
    def __init__(self):
        self.said = []

    async def speak(self, *, tts_text, **_):
        self.said.append(tts_text)


def sentence(text):
    return SentenceOutput(
        display_text=DisplayText(text=text), tts_text=text, actions=Actions()
    )


async def _send(_):
    return None


def test_sentences_are_translated_together_and_spoken_in_order():
    translator, speaker = SlowTranslator(), Speaker()

    async def scenario():
        def say(text, after):
            return asyncio.create_task(
                handle_sentence_output(
                    sentence(text),
                    None,
                    None,
                    _send,
                    speaker,
                    translator,
                    voice_lang="ja",
                    after=after,
                )
            )

        begun = time.monotonic()
        first = say("第一句話比較長，翻得比較慢。", None)
        second = say("第二句很短。", first)
        said = [await first, await second]
        return said, time.monotonic() - begun

    said, took = asyncio.run(scenario())

    assert said == ["第一句話比較長，翻得比較慢。", "第二句很短。"]
    assert speaker.said == ["訳:第一句話比較長，翻得比較慢。", "訳:第二句很短。"]
    # 第二句在第一句還在翻的時候就開始翻了。
    assert (
        translator.started["第二句很短。"]
        < translator.finished["第一句話比較長，翻得比較慢。"]
    )
    assert took < 0.48
