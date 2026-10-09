"""一句太長還沒結束，就在逗號先切一段送出去合成。

只認句號、驚嘆號、問號的話，「辛苦啦……既然這麼累，週末就別想太多要去哪裡了，
先在星穹列車上好好睡一覺，把精神養足比較重要喔！」整段只有逗號，要等她全部寫完
才開始翻譯（7 秒）與合成（6 秒），第一個聲音 24 秒。
"""

import asyncio

from src.open_llm_vtuber.utils.sentence_divider import (
    LONG_CLAUSE_CHARS,
    SentenceDivider,
    long_clause_split,
)

REPLY = "辛苦啦……既然這麼累，週末就別想太多要去哪裡了，先在星穹列車上好好睡一覺，把精神養足比較重要喔！"


def divide(text):
    async def tokens():
        for ch in text:
            yield ch

    async def collect():
        divider = SentenceDivider(faster_first_response=False, segment_method="regex")
        return [s.text async for s in divider.process_stream(tokens())]

    return asyncio.run(collect())


def test_a_long_sentence_is_cut_at_the_comma_after_the_limit():
    parts = divide(REPLY)
    assert "".join(parts) == REPLY
    assert len(parts) >= 2
    assert all(len(p) >= LONG_CLAUSE_CHARS for p in parts[:-1])
    assert parts[0].endswith("，")


def test_short_sentences_are_not_cut():
    assert divide("好喔，那就這樣吧。我們走！") == ["好喔，那就這樣吧。", "我們走！"]


def test_no_cut_inside_an_open_tag():
    assert long_clause_split("[joy:0.6，好多字好多字好多字好多字好多字，") is None


def test_no_cut_before_the_limit():
    assert long_clause_split("短短的，還沒到") is None
