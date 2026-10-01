"""模型多打的符號，在斷句之前就收掉。

2026-10-01 兩個情境實測，212 則回覆裡 84 則有 `*忍不住縮成一團，**有點抖*` 這種寫法：
同一段動作，在逗號後面多打兩個星號。字幕上多出 `*`，TTS 把後半段「有點抖」當成台詞
唸出來。另有 11 則把「」當說話的引號，卻漏了第一個開引號：`……誰會問啊！」*動作*  「……`。
"""

import asyncio

from src.open_llm_vtuber.agent.transformers import MarkTidier, tidy_marks
from src.open_llm_vtuber.utils.tts_preprocessor import TTSFilterState, filter_asterisks


def test_two_asterisks_inside_an_action_are_one_action():
    text = "*忍不住縮成一團，**有點抖*對喔！上次那個結局真的超嚇人的。"

    tidied = tidy_marks(text)

    assert tidied == "*忍不住縮成一團，有點抖*對喔！上次那個結局真的超嚇人的。"
    # 語音那側：整段動作都不唸。
    assert (
        filter_asterisks(tidied, TTSFilterState()) == "對喔！上次那個結局真的超嚇人的。"
    )


def test_it_works_on_a_stream_cut_anywhere():
    tidier = MarkTidier()
    pieces = ["*眼神閃躲了一下，*", "*手指無意識", "地搓著衣角*關於連動", "的事……"]

    out = "".join(tidier.feed(piece) for piece in pieces) + tidier.finish()

    assert out == "*眼神閃躲了一下，手指無意識地搓著衣角*關於連動的事……"


def test_a_closing_quote_with_no_opening_one_is_dropped():
    text = "最討厭誰？哼，這種問題誰會問啊！」*把法杖往地上一杵*  「我討厭的人……大概只有『冰系』傢伙吧。」"

    assert tidy_marks(text) == (
        "最討厭誰？哼，這種問題誰會問啊！*把法杖往地上一杵*  「我討厭的人……大概只有『冰系』傢伙吧。」"
    )


def test_what_was_written_right_is_left_alone():
    for text in (
        "*把法杖往肩上一扛*好，走吧。*回頭看了你一眼*",
        "下一站是「熔岩裂谷」，『冰系』魔物最討厭了。",
        "一，二，三。",
        "她說：「快跑！」然後就不見了。",
    ):
        assert tidy_marks(text) == text


def test_the_sentence_pipeline_gets_the_tidied_text():
    from src.open_llm_vtuber.agent.transformers import sentence_divider

    @sentence_divider(faster_first_response=False, segment_method="regex")
    async def reply():
        for piece in ["*托著下巴，", "**眼神飄向上方*月亮上很冷喔。"]:
            yield piece

    async def collect():
        return [item.text async for item in reply()]

    assert "".join(asyncio.run(collect())) == "*托著下巴，眼神飄向上方*月亮上很冷喔。"


def test_what_she_remembers_saying_is_the_tidied_text(tmp_path):
    """她讀到自己上一句多打的符號，下一句就照著打。"""
    import pytest

    pytest.importorskip("ai_character_engine")
    from tests.test_engine_agent import EngineLLM, agent, companion

    current = agent(companion(tmp_path, EngineLLM()))

    assert (
        current._remembered("*托著下巴，**眼神飄向上方*很冷喔。」")
        == "*托著下巴，眼神飄向上方*很冷喔。"
    )
