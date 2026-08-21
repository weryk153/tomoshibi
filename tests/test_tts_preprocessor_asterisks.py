"""
Tests for the asterisk (stage-direction) stripping bug in tts_preprocessor.

Background: `sentence_divider` splits a streamed reply into fragments on
punctuation - including commas - before `tts_filter` ever runs. That means
a stage direction containing a comma, e.g. `*歪頭，眼神帶著一絲困惑* 什麼？`, can be
cut into two fragments, each carrying only one asterisk of the pair. The old
`filter_asterisks(text)` only matched *paired* asterisks within a single
call, so an unpaired asterisk in a fragment was left completely unfiltered
- the stage direction got spoken aloud (and translated).

The fix makes the filter stateful across fragments of the same response via
`TTSFilterState`, so an asterisk opened in one fragment is remembered and
its matching content is still dropped when the closing asterisk shows up in
a later fragment.
"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.utils.tts_preprocessor import (
    TTSFilterState,
    filter_asterisks,
    filter_brackets,
    tts_filter,
)
from src.open_llm_vtuber.agent.transformers import tts_filter as tts_filter_decorator
from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.utils.sentence_divider import SentenceWithTags, TagInfo, TagState


def _kwargs(**overrides):
    base = dict(
        remove_special_char=False,
        ignore_brackets=False,
        ignore_parentheses=False,
        ignore_asterisks=True,
        ignore_angle_brackets=False,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# The exact real-world failures from the bug report
# ---------------------------------------------------------------------------


def test_paired_asterisks_within_one_fragment_are_stripped():
    state = TTSFilterState()
    result = filter_asterisks("*歪頭，眼神帶著一絲困惑* 什麼？", state)
    assert result == "什麼？"
    # Fully paired within the fragment - nothing left open.
    assert state.in_asterisk is False


def test_fragment_with_only_opening_asterisk_is_fully_suppressed():
    """
    Reproduces the bug: '*歪頭，' used to pass through unchanged because the
    regex-based filter required a matching close in the same call.
    """
    state = TTSFilterState()
    result = filter_asterisks("*歪頭,", state)
    assert result == ""
    assert state.in_asterisk is True


def test_fragment_with_only_closing_asterisk_is_fully_suppressed_up_to_close():
    """
    Reproduces the bug: '眼神帶著一絲困惑* 什麼?' used to pass through unchanged
    because there was no opening asterisk in the same call to pair with.
    Here we simulate arriving in an already-open region (as would happen
    right after the fragment from the previous test).
    """
    state = TTSFilterState(in_asterisk=True)
    result = filter_asterisks("眼神帶著一絲困惑* 什麼?", state)
    assert result == "什麼?"
    assert state.in_asterisk is False


def test_comma_split_stage_direction_across_two_fragments_end_to_end():
    """
    The two bug fragments back-to-back, sharing one TTSFilterState, exactly
    as tts_filter's decorator would apply them across a stream.
    """
    state = TTSFilterState()
    first = filter_asterisks("*歪頭,", state)
    second = filter_asterisks("眼神帶著一絲困惑* 什麼?", state)
    assert first == ""
    assert second == "什麼?"
    assert state.in_asterisk is False


# ---------------------------------------------------------------------------
# Additional required coverage
# ---------------------------------------------------------------------------


def test_stage_direction_split_across_three_fragments():
    state = TTSFilterState()
    f1 = filter_asterisks("*歪頭，", state)
    f2 = filter_asterisks("仍然一臉困惑，", state)
    f3 = filter_asterisks("沒有回答* 什麼？", state)
    assert (f1, f2, f3) == ("", "", "什麼？")
    assert state.in_asterisk is False


def test_unterminated_asterisk_at_end_of_stream_does_not_leak():
    """
    An asterisk left open at the end of one response must not swallow the
    next response. A fresh TTSFilterState (as created per-stream by the
    tts_filter decorator in transformers.py) is what guarantees the reset.
    """
    state = TTSFilterState()
    tail = filter_asterisks("嗯*突然停下不動", state)
    assert tail == "嗯"
    assert state.in_asterisk is True

    # Simulate the next response getting a brand-new state, exactly as
    # transformers.tts_filter's wrapper() does on every new invocation.
    next_state = TTSFilterState()
    next_reply = filter_asterisks("哈囉，你好呀！", next_state)
    assert next_reply == "哈囉，你好呀！"
    assert next_state.in_asterisk is False


def test_double_asterisk_bold_markers_are_stripped():
    state = TTSFilterState()
    result = filter_asterisks("**bold** text", state)
    assert result == "text"
    assert state.in_asterisk is False


def test_triple_asterisk_markers_are_stripped():
    state = TTSFilterState()
    result = filter_asterisks("***bold*** text", state)
    assert result == "text"
    assert state.in_asterisk is False


def test_reply_with_no_asterisks_passes_through_byte_identical():
    state = TTSFilterState()
    text = "你好，世界！  今天天氣不錯。"
    result = filter_asterisks(text, state)
    assert result == text
    assert state.in_asterisk is False


def test_reply_with_no_asterisks_passes_through_byte_identical_via_tts_filter():
    """Same check through the public tts_filter() entrypoint."""
    text = "你好，世界！  今天天氣不錯。"
    result = tts_filter(text=text, **_kwargs())
    assert result == text


# ---------------------------------------------------------------------------
# tts_filter() integration - state threading, and streaming behavior
# ---------------------------------------------------------------------------


def test_tts_filter_end_to_end_defaults_to_fresh_state_each_call():
    """
    Calling tts_filter() without an explicit `state` must behave like the
    old stateless function for a single, self-contained fragment (i.e.
    still correctly strips a fully-paired asterisk region).
    """
    result = tts_filter(text="*歪頭，眼神帶著一絲困惑* 什麼？", **_kwargs())
    assert result == "什麼？"


def test_tts_filter_threads_shared_state_across_calls():
    state = TTSFilterState()
    first = tts_filter(text="*歪頭,", state=state, **_kwargs())
    second = tts_filter(text="眼神帶著一絲困惑* 什麼?", state=state, **_kwargs())
    assert first == ""
    assert second == "什麼?"


# ---------------------------------------------------------------------------
# Bracket/parenthesis/angle-bracket variants share the same pairing shape.
# We fixed them alongside asterisks using the same stateful mechanism.
# ---------------------------------------------------------------------------


def test_brackets_split_across_fragments_are_also_fixed():
    state = TTSFilterState()
    first = filter_brackets("[whisper,", state)
    second = filter_brackets("still thinking] hello", state)
    assert first == ""
    assert second == "hello"
    assert state.bracket_depth == 0


# ---------------------------------------------------------------------------
# transformers.tts_filter decorator - the actual streaming integration point.
# These exercise the decorator exactly as basic_memory_agent.py / letta_agent
# use it: `chat` is decorated once, and the decorated generator is invoked
# fresh per response. They also pin down the "subtitles/memory must not
# change" requirement at the point where display_text and tts_text diverge.
# ---------------------------------------------------------------------------


def _fake_tts_config(**overrides):
    base = dict(
        remove_special_char=False,
        ignore_brackets=False,
        ignore_parentheses=False,
        ignore_asterisks=True,
        ignore_angle_brackets=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _sentence_with_no_tag(text: str) -> SentenceWithTags:
    return SentenceWithTags(text=text, tags=[TagInfo("", TagState.NONE)])


async def _fake_upstream_stream(fragments):
    """Stands in for sentence_divider -> actions_extractor -> display_processor."""
    for text in fragments:
        yield _sentence_with_no_tag(text), DisplayText(text=text), Actions()


async def _run_decorated(decorated, fragments):
    results = []
    async for item in decorated(fragments):
        results.append(item)
    return results


async def _run_tts_filter_decorator(fragments, config=None):
    decorated = tts_filter_decorator(config or _fake_tts_config())(
        _fake_upstream_stream
    )
    return await _run_decorated(decorated, fragments)


def test_decorator_display_text_is_untouched_while_tts_text_is_filtered():
    """
    The canonical reply (subtitle/history) must never be mutated by the TTS
    asterisk filter - only SentenceOutput.tts_text should differ from the
    display text.
    """
    outputs = asyncio.run(
        _run_tts_filter_decorator(["*歪頭,", "眼神帶著一絲困惑* 什麼?"])
    )
    assert [o.display_text.text for o in outputs] == [
        "*歪頭,",
        "眼神帶著一絲困惑* 什麼?",
    ]
    assert [o.tts_text for o in outputs] == ["", "什麼?"]


def test_decorator_resets_asterisk_state_between_separate_responses():
    """
    In production the decorator is applied ONCE, at agent construction time
    (`self.chat = self._chat_function_factory()` in basic_memory_agent.py /
    letta_agent.py), and the resulting decorated generator function is then
    invoked fresh for every conversation turn (`context.agent_engine.chat(
    batch_input)` in single_conversation.py / group_conversation.py). So
    this test decorates once and calls the SAME decorated function twice -
    matching production - rather than re-decorating per response, which
    would trivially get a fresh state regardless of whether the fix resets
    correctly.

    An unterminated asterisk left open at the end of response 1 must not
    suppress any of response 2's TTS text.
    """
    decorated = tts_filter_decorator(_fake_tts_config())(_fake_upstream_stream)

    response_1 = asyncio.run(_run_decorated(decorated, ["嗯*突然停下不動"]))
    assert response_1[0].tts_text == "嗯"
    assert response_1[0].display_text.text == "嗯*突然停下不動"

    # A second, independent call to the SAME decorated function - simulating
    # the next conversation turn - must start with a clean state.
    response_2 = asyncio.run(_run_decorated(decorated, ["哈囉，你好呀！"]))
    assert response_2[0].tts_text == "哈囉，你好呀！"
    assert response_2[0].display_text.text == "哈囉，你好呀！"


def test_full_width_parentheses_are_filtered_like_half_width():
    """中文本來就用全形括號，模型自己就會產出。

    只認半形的話，全形的動作描述會被當成台詞送去翻譯＋合成——實測一輪回覆裡
    每個動作描述多付一次翻譯（3～9 秒）加一次 TTS，這正是「回應速度很慢」的
    一大來源。
    """
    assert (
        tts_filter(
            text="（仔細掃視畫面，眉頭微微皺起）這跟生意還有距離呢。",
            remove_special_char=True,
            ignore_brackets=True,
            ignore_parentheses=True,
            ignore_asterisks=True,
            ignore_angle_brackets=True,
        ).strip()
        == "這跟生意還有距離呢。"
    )


def test_both_paren_widths_in_one_line():
    assert (
        tts_filter(
            text="（全形）中間(半形)結尾。",
            remove_special_char=True,
            ignore_brackets=True,
            ignore_parentheses=True,
            ignore_asterisks=True,
            ignore_angle_brackets=True,
        ).strip()
        == "中間結尾。"
    )


def test_text_without_parentheses_is_untouched():
    """過濾不能吃掉正常台詞——那比漏掉動作描述嚴重得多。"""
    line = "這跟「生意」還有一段距離呢。"
    assert (
        tts_filter(
            text=line,
            remove_special_char=True,
            ignore_brackets=True,
            ignore_parentheses=True,
            ignore_asterisks=True,
            ignore_angle_brackets=True,
        ).strip()
        == line
    )
