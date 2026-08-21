"""An LLM failure notice must not be stored as a turn by the character.

When a chat completion raises, the stateless LLM layers yield an English
sentence instead of propagating the exception, so the pipeline keeps running.
That sentence then travels like ordinary speech: spoken by TTS, written to chat
history as an assistant turn, and read back as context on later turns.

Measured on this machine before the guard: 75 of 231 stored assistant turns
across 9 history files were exactly this sentence. A model reading that history
sees its own past turns as English error text.

The human side is deliberately NOT filtered — whatever the user typed is what
they typed, even if it happens to look like an error.
"""

import json

import pytest

from src.open_llm_vtuber.chat_history_manager import (
    create_new_history,
    get_history,
    get_history_list,
    store_message,
)
from src.open_llm_vtuber.llm_error_sentinel import is_llm_error_placeholder

CHAT_ENDPOINT_ERROR = (
    "Error calling the chat endpoint: Error occurred while generating response. "
    "See the logs for details."
)
CONNECTION_ERROR = (
    "Error calling the chat endpoint: Connection error. Failed to connect to the "
    "LLM API. \nCheck the configurations and the reachability of the LLM backend."
)


@pytest.fixture
def history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    uid = create_new_history("testconf")
    return "testconf", uid


def _read(conf_uid: str, history_uid: str) -> list:
    import glob

    paths = glob.glob(f"chat_history/{conf_uid}/*{history_uid}*.json")
    assert paths, "history file was not created"
    return json.load(open(paths[0], encoding="utf-8"))


def test_the_error_placeholder_is_not_written_as_an_assistant_turn(history):
    conf_uid, history_uid = history

    store_message(conf_uid, history_uid, "ai", CHAT_ENDPOINT_ERROR)

    stored = [m for m in _read(conf_uid, history_uid) if m.get("role") == "ai"]
    assert stored == []


def test_the_connection_error_variant_is_also_recognised(history):
    """The connection variant appends the endpoint, cause and a docs URL, so the
    check has to match a prefix rather than the whole sentence."""
    conf_uid, history_uid = history

    store_message(conf_uid, history_uid, "ai", CONNECTION_ERROR)

    assert [m for m in _read(conf_uid, history_uid) if m.get("role") == "ai"] == []


def test_real_speech_is_still_stored(history):
    """The guard must not eat ordinary replies — that would be far worse than
    the problem it fixes."""
    conf_uid, history_uid = history

    store_message(conf_uid, history_uid, "ai", "今天天氣很好，我們出去走走吧。")

    stored = [m for m in _read(conf_uid, history_uid) if m.get("role") == "ai"]
    assert len(stored) == 1
    assert stored[0]["content"] == "今天天氣很好，我們出去走走吧。"


def test_translated_display_copy_does_not_replace_canonical_history(history):
    conf_uid, history_uid = history

    store_message(
        conf_uid,
        history_uid,
        "ai",
        "これは日本語です。",
        display_content="這是日文。",
    )

    stored = get_history(conf_uid, history_uid)[0]
    assert stored["content"] == "これは日本語です。"
    assert stored["display_content"] == "這是日文。"
    assert get_history_list(conf_uid)[0]["latest_message"]["content"] == "這是日文。"


def test_a_reply_that_merely_mentions_an_error_is_kept(history):
    """The character discussing an error is speech, not a backend failure.

    The quoted text includes the colon, so this only passes with a prefix match:
    a substring check would swallow the reply. An earlier version of this test
    used a full-width comma instead and therefore proved nothing.
    """
    conf_uid, history_uid = history
    line = "你剛才看到的「Error calling the chat endpoint: ...」通常是後端沒起來。"

    store_message(conf_uid, history_uid, "ai", line)

    stored = [m for m in _read(conf_uid, history_uid) if m.get("role") == "ai"]
    assert len(stored) == 1


def test_the_user_side_is_never_filtered(history):
    """Whatever the user typed is what they typed."""
    conf_uid, history_uid = history

    store_message(conf_uid, history_uid, "human", CHAT_ENDPOINT_ERROR)

    stored = [m for m in _read(conf_uid, history_uid) if m.get("role") == "human"]
    assert len(stored) == 1


def test_detector_ignores_empty_and_none():
    assert is_llm_error_placeholder("") is False
    assert is_llm_error_placeholder(None) is False
