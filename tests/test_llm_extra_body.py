"""extra_body passthrough 測試。

守住一個具體的失效模式：factory 是逐一列舉 kwargs 而非展開整個 config，
少加一行參數就會讓設定靜默失效——設定看起來生效了，實際上沒送出去。
"""

import asyncio

from src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm import AsyncLLM
from src.open_llm_vtuber.agent.stateless_llm_factory import LLMFactory
from src.open_llm_vtuber.config_manager.stateless_llm import (
    LmStudioConfig,
    OpenAICompatibleConfig,
)

REASONING_OFF = {"reasoning_effort": "none"}


class _EmptyStream:
    """空的 async stream：不產生任何 chunk，並支援 chat_completion 的 finally 收尾。"""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    async def close(self):
        return None


class _FakeCompletions:
    def __init__(self, captured: dict):
        self._captured = captured

    async def create(self, **kwargs):
        self._captured.update(kwargs)
        return _EmptyStream()


class _FakeClient:
    def __init__(self, captured: dict):
        self.chat = type("_Chat", (), {"completions": _FakeCompletions(captured)})()


def test_config_accepts_extra_body():
    config = OpenAICompatibleConfig(
        base_url="http://localhost:1234/v1",
        llm_api_key="k",
        model="qwen/qwen3.5-9b",
        extra_body=REASONING_OFF,
    )
    assert config.extra_body == REASONING_OFF


def test_config_extra_body_defaults_to_none():
    config = OpenAICompatibleConfig(
        base_url="http://localhost:1234/v1",
        llm_api_key="k",
        model="qwen/qwen3.5-9b",
    )
    assert config.extra_body is None


def test_lmstudio_config_inherits_extra_body():
    config = LmStudioConfig(model="qwen/qwen3.5-9b", extra_body=REASONING_OFF)
    assert config.extra_body == REASONING_OFF


def test_factory_passes_extra_body_through():
    llm = LLMFactory.create_llm(
        llm_provider="lmstudio_llm",
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        llm_api_key="k",
        organization_id=None,
        project_id=None,
        temperature=1.0,
        extra_body=REASONING_OFF,
    )
    assert llm.extra_body == REASONING_OFF


def test_extra_body_reaches_create_call():
    captured = {}
    llm = AsyncLLM(
        model="qwen/qwen3.5-9b",
        base_url="http://localhost:1234/v1",
        extra_body=REASONING_OFF,
    )
    llm.client = _FakeClient(captured)

    async def drain():
        async for _ in llm.chat_completion([{"role": "user", "content": "hi"}]):
            pass

    asyncio.run(drain())
    assert captured["extra_body"] == REASONING_OFF


def test_extra_body_absent_when_not_configured():
    captured = {}
    llm = AsyncLLM(model="qwen/qwen3.5-9b", base_url="http://localhost:1234/v1")
    llm.client = _FakeClient(captured)

    async def drain():
        async for _ in llm.chat_completion([{"role": "user", "content": "hi"}]):
            pass

    asyncio.run(drain())
    assert "extra_body" not in captured
