"""The cache measurement splits LM Studio's prompt-cache lines into conversation and background requests."""

from scripts.measure_prompt_cache import summarize

LINES = [
    "[coordinator][INFO]: Prompt cache restore: cached_tokens=2816 uncached_tokens=223 lifetime_efficiency=79.71%",
    "[coordinator][INFO]: Prompt cache restore: cached_tokens=2560 uncached_tokens=1900 lifetime_efficiency=70.00%",
    "[coordinator][INFO]: Prompt cache restore: cached_tokens=256 uncached_tokens=300 lifetime_efficiency=40.00%",
    "something else entirely",
]


def test_requests_are_split_by_total_size_and_summarized():
    summary = summarize(LINES)
    assert summary["conversation"]["n"] == 2
    assert summary["conversation"]["median"] == 1061.5
    assert summary["conversation"]["max"] == 1900
    assert summary["background"]["n"] == 1
    assert summary["background"]["max"] == 300
