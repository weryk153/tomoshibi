"""她回不了話時，告訴使用者是哪裡出問題、怎麼修，不是只丟一句 Character processing failed。"""

import httpx
import openai
import pytest
from ai_character_engine.host.bridge import HostBridgeError
from ai_character_engine.llm.errors import LLMError

from src.open_llm_vtuber.llm_errors import describe_llm_failure

REQUEST = httpx.Request("POST", "http://localhost:11434/v1/chat/completions")


def wrapped(cause):
    """引擎實際丟上來的樣子：HostBridgeError ← LLMError ← 供應商的錯誤。"""
    try:
        try:
            try:
                raise cause
            except Exception as exc:
                raise LLMError("ollama_llm streaming provider call failed") from exc
        except Exception as exc:
            raise HostBridgeError(
                "Character processing failed. Check the configured providers."
            ) from exc
    except HostBridgeError as error:
        return error


SETTINGS = dict(
    provider="ollama_llm", base_url="http://localhost:11434/v1", model="qwen2.5:3b"
)


def test_a_model_server_that_is_not_running_is_named_with_its_address():
    got = describe_llm_failure(
        wrapped(openai.APIConnectionError(request=REQUEST)), **SETTINGS
    )
    assert got["text_key"] == "errors.llmUnreachable"
    assert got["params"] == {
        "provider": "Ollama",
        "url": "http://localhost:11434/v1",
        "model": "qwen2.5:3b",
    }
    assert "Ollama" in got["message"] and "localhost:11434" in got["message"]


def test_a_missing_model_a_refused_key_and_a_timeout_each_say_so():
    response = httpx.Response(404, request=REQUEST)
    missing = openai.NotFoundError(
        "model 'qwen2.5:3b' not found", response=response, body=None
    )
    assert (
        describe_llm_failure(wrapped(missing), **SETTINGS)["text_key"]
        == "errors.llmModelMissing"
    )
    refused = openai.AuthenticationError(
        "bad key", response=httpx.Response(401, request=REQUEST), body=None
    )
    assert (
        describe_llm_failure(wrapped(refused), **SETTINGS)["text_key"]
        == "errors.llmAuth"
    )
    slow = openai.APITimeoutError(request=REQUEST)
    assert (
        describe_llm_failure(wrapped(slow), **SETTINGS)["text_key"]
        == "errors.llmTimeout"
    )


def test_other_failures_are_left_as_they_were():
    assert (
        describe_llm_failure(wrapped(ValueError("something else")), **SETTINGS) is None
    )
    assert describe_llm_failure(RuntimeError("plain"), **SETTINGS) is None


@pytest.mark.parametrize(
    "provider,label",
    [
        ("lmstudio_llm", "LM Studio"),
        ("openai_compatible_llm", "OpenAI-compatible"),
        ("weird_llm", "weird_llm"),
    ],
)
def test_providers_are_named_the_way_the_settings_page_names_them(provider, label):
    got = describe_llm_failure(
        wrapped(openai.APIConnectionError(request=REQUEST)),
        provider=provider,
        base_url="u",
        model="m",
    )
    assert got["params"]["provider"] == label
