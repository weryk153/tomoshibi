"""情緒關鍵字要撐過整則回覆。

提示詞要求關鍵字整則只寫一個、而且寫在最前面（寫在最後表情會來不及顯示）。
但語音是一句一句合成的，只有第一句拿得到那個關鍵字——不記住的話，後面每一句
都會退回預設參考音，一則回覆裡聲音會從有情緒變回平的。
"""

import asyncio

from src.open_llm_vtuber.agent.transformers import actions_extractor
from src.open_llm_vtuber.utils.sentence_divider import SentenceWithTags


class _FakeLive2D:
    """[happy] 只出現在第一句，就像真實的回覆那樣。"""

    @staticmethod
    def extract_emotion(text):
        return [3] if "[happy]" in text else []

    @staticmethod
    def extract_emotion_intensities(text):
        # 跟 extract_emotion 一一對應。這個替身只用不帶強度的 [happy]，所以永遠是滿的。
        return [1.0] if "[happy]" in text else []

    @staticmethod
    def extract_emotion_keys(text):
        return ["happy"] if "[happy]" in text else []

    @staticmethod
    def extract_motions(_text):
        return []


def _collect(sentences):
    @actions_extractor(_FakeLive2D())
    async def stream():
        for text in sentences:
            yield SentenceWithTags(text=text, tags=[])

    async def run():
        return [actions async for _sentence, actions in stream()]

    return asyncio.run(run())


def test_emotion_carries_to_later_sentences():
    got = _collect(["[happy]今天超順的。", "程式一次就過了。", "難得。"])
    assert [a.emotion for a in got] == ["happy", "happy", "happy"]


def test_expressions_still_only_on_the_first_sentence():
    """表情是一次性的事件，不該跟著每句重送——那會讓臉一直重設。"""
    got = _collect(["[happy]今天超順的。", "程式一次就過了。"])
    assert got[0].expressions == [3]
    assert got[1].expressions is None


def test_no_emotion_stays_none():
    got = _collect(["普通的一句話。", "還是普通。"])
    assert [a.emotion for a in got] == [None, None]


def test_emotion_does_not_leak_across_replies():
    """每則回覆重新開始——上一則的語氣不能滲進下一則。"""
    first = _collect(["[happy]開心。", "很開心。"])
    second = _collect(["這是新的一則。"])
    assert first[-1].emotion == "happy"
    assert second[0].emotion is None


def test_later_keyword_updates_the_emotion():
    """模型沒守規則、中途又寫了一個時，以最新的為準。"""
    got = _collect(["普通。", "[happy]突然開心。", "接下去。"])
    assert [a.emotion for a in got] == [None, "happy", "happy"]
