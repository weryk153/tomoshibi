"""The verdict rule behind POST /api/translator-config/test.

Everything about cross-language voice fails silently. LLMTranslate catches every
exception — a reasoning model that leaves `content` empty, a timeout, a wrong
endpoint, a wrong model name — and returns its input verbatim. The character
then speaks untranslated text with no error anywhere on screen, which looks
exactly like "translation is switched off".

So "output equals input" is the only evidence a caller has that nothing
happened. If that check is ever relaxed, the test button reports success for a
translator that is doing nothing at all — worse than having no button, because
it actively tells the user the thing they are debugging is fine.
"""

from src.open_llm_vtuber.translator_route import (
    TRANSLATOR_TEST_SAMPLE,
    classify_translation_test,
)


def test_a_real_translation_passes():
    ok, reason = classify_translation_test(
        TRANSLATOR_TEST_SAMPLE,
        "今日は天気がいいですね、外へ出かけて行きましょうか。",
    )

    assert ok is True
    assert reason == "ok"


def test_text_returned_verbatim_is_reported_as_a_failure():
    """The fallback path: LLMTranslate handed the input straight back."""
    ok, reason = classify_translation_test(
        TRANSLATOR_TEST_SAMPLE, TRANSLATOR_TEST_SAMPLE
    )

    assert ok is False
    assert reason == "unchanged"


def test_surrounding_whitespace_does_not_disguise_a_fallback():
    """`.strip()` on the response is what stops a stray newline from reading as
    a successful translation."""
    ok, reason = classify_translation_test(
        TRANSLATOR_TEST_SAMPLE, f"\n  {TRANSLATOR_TEST_SAMPLE}  \n"
    )

    assert ok is False
    assert reason == "unchanged"


def test_an_empty_response_classifies_as_changed():
    """Documents a known boundary rather than a desirable outcome.

    An empty string is not equal to the sample, so it reads as "ok". That is
    acceptable only because LLMTranslate can never produce it: its own
    empty-content branch already falls back to the original text, which lands in
    the "unchanged" case above. If that fallback is ever removed, this
    classification becomes wrong and this test is where it shows up.
    """
    assert classify_translation_test(TRANSLATOR_TEST_SAMPLE, "") == (True, "ok")


def test_the_sample_is_long_enough_to_change_under_translation():
    """A one-word sample could legitimately translate to itself and would make
    the whole check unreliable, so the sample has to be a real sentence."""
    assert len(TRANSLATOR_TEST_SAMPLE) >= 8
    assert "，" in TRANSLATOR_TEST_SAMPLE or "。" in TRANSLATOR_TEST_SAMPLE
