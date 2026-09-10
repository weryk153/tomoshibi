from types import SimpleNamespace

import pytest

from src.open_llm_vtuber.memory_core import resolve_consolidation_llm


def _character(provider: str):
    return SimpleNamespace(
        agent_config=SimpleNamespace(
            agent_settings=SimpleNamespace(
                basic_memory_agent=SimpleNamespace(llm_provider=provider),
            ),
            llm_configs=SimpleNamespace(
                openai_compatible_llm=SimpleNamespace(
                    base_url="http://ollama:11434/v1",
                    model="old-model",
                    llm_api_key="old-key",
                ),
                lmstudio_llm=SimpleNamespace(
                    base_url="http://lmstudio:1234/v1",
                    model="active-model",
                    llm_api_key="active-key",
                    extra_body={"reasoning_effort": "none", "top_p": 0.8},
                ),
                llama_cpp_llm=SimpleNamespace(model_path="model.gguf"),
            ),
        )
    )


def test_memory_consolidation_uses_the_active_provider():
    assert resolve_consolidation_llm(_character("lmstudio_llm")) == (
        "http://lmstudio:1234/v1",
        "active-model",
        "active-key",
        {"reasoning_effort": "none", "top_p": 0.8},
    )


def test_memory_consolidation_without_extra_body_yields_empty_dict():
    """openai_compatible_llm 這組沒設 extra_body，路徑必須照常可用。"""
    assert resolve_consolidation_llm(_character("openai_compatible_llm")) == (
        "http://ollama:11434/v1",
        "old-model",
        "old-key",
        {},
    )


def test_consolidation_payload_carries_extra_body(monkeypatch, tmp_path):
    """整理呼叫必須帶上對話 LLM 的 extra_body。

    漏掉它就是這個功能從未寫出任何記憶的根因：conf 靠
    extra_body.reasoning_effort='none' 關掉 Qwen3.5 的思考模式，
    整理路徑沒抄到，於是每次都思考到超過 60 秒 timeout，
    再被 fail-soft 靜默吞掉——log 只剩一行空訊息的 warning。
    """
    import asyncio
    import src.open_llm_vtuber.memory_core as mc

    captured = {}

    class _Resp:
        def json(self):
            return {"choices": [{"message": {"content": "- 使用者在做 Live2D"}}]}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            captured.update(json)
            return _Resp()

    monkeypatch.setattr(mc.httpx, "AsyncClient", _Client)
    monkeypatch.setattr(
        mc, "_memory_file", lambda conf_uid, history_uid: tmp_path / "core_memory.md"
    )

    asyncio.run(
        mc.consolidate_core_memory(
            "aoi",
            "conv-1",
            "我在做 Live2D",
            "加油",
            "http://x/v1",
            "m",
            extra_body={"reasoning_effort": "none"},
        )
    )

    assert captured.get("reasoning_effort") == "none"
    assert (tmp_path / "core_memory.md").read_text(
        encoding="utf-8"
    ) == "- 使用者在做 Live2D"


def test_memory_consolidation_rejects_non_compatible_provider():
    with pytest.raises(ValueError, match="not OpenAI-compatible"):
        resolve_consolidation_llm(_character("llama_cpp_llm"))
