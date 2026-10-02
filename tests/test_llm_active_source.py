"""語言模型頁最上面那行「目前使用」：讀的是 llm_provider 真正指向的那一塊。

以前這一頁不管用的是哪一塊，都顯示 openai_compatible_llm 那塊的值——偵測套用了
本機 9B，下面卻還寫著 OpenRouter 的 Gemma，看不出到底在用什麼。
"""

import pytest

from src.open_llm_vtuber.llm_config_route import active_llm


def conf(provider, **blocks):
    llm_configs = {
        "openai_compatible_llm": {
            "base_url": "https://openrouter.ai/api/v1",
            "model": "google/gemma-4-31b-it:free",
        },
        "lmstudio_llm": {
            "base_url": "http://127.0.0.1:1234/v1",
            "model": "qwen/qwen3.5-9b",
        },
        "ollama_llm": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:3b"},
        "claude_llm": {"model": "claude-x"},
        **blocks,
    }
    return {
        "character_config": {
            "agent_config": {
                "agent_settings": {"conversation": {"llm_provider": provider}},
                "llm_configs": llm_configs,
            }
        }
    }


@pytest.mark.parametrize(
    "provider,blocks,expected",
    [
        (
            "lmstudio_llm",
            {},
            ("local", None, "qwen/qwen3.5-9b", "http://127.0.0.1:1234/v1"),
        ),
        ("ollama_llm", {}, ("ollama", None, "qwen2.5:3b", "http://localhost:11434/v1")),
        (
            "openai_compatible_llm",
            {},
            (
                "custom",
                None,
                "google/gemma-4-31b-it:free",
                "https://openrouter.ai/api/v1",
            ),
        ),
        (
            "openai_compatible_llm",
            {
                "openai_compatible_llm": {
                    "base_url": "https://api.openai.com/v1/",
                    "model": "gpt-x",
                }
            },
            ("apikey", "openai", "gpt-x", "https://api.openai.com/v1/"),
        ),
        (
            "openai_compatible_llm",
            {
                "openai_compatible_llm": {
                    "base_url": "http://localhost:11434/v1",
                    "model": "llama3",
                }
            },
            ("ollama", None, "llama3", "http://localhost:11434/v1"),
        ),
        ("claude_llm", {}, ("other", None, "claude-x", "")),
    ],
)
def test_the_source_in_use(provider, blocks, expected):
    active = active_llm(conf(provider, **blocks))
    assert (
        active["source"],
        active["api_provider"],
        active["model"],
        active["base_url"],
    ) == expected
    assert active["provider"] == provider


def test_nothing_selected_means_the_openai_block():
    data = conf("openai_compatible_llm")
    del data["character_config"]["agent_config"]["agent_settings"]
    assert active_llm(data)["provider"] == "openai_compatible_llm"
