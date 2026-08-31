"""把設定寫進「偵測到的那個」供應商區塊，而不是固定的那一個。

原本的 _write_openai_block 固定寫 openai_compatible_llm 並強制切換 llm_provider。
偵測到 LM Studio 時那是錯的目標：使用者會被導向一個沒有 extra_body 的區塊，於是
思考模式沒被關掉——正好是自動設定想避免的那個故障。
"""

import pytest

from src.open_llm_vtuber import llm_config_route as route
from src.open_llm_vtuber import conf_editor

CONF = """character_config:
  agent_config:
    conversation_agent_choice: 'basic_memory_agent'
    agent_settings:
      basic_memory_agent:
        llm_provider: 'openai_compatible_llm'
    llm_configs:
      openai_compatible_llm:
        base_url: 'http://localhost:11434/v1'
        model: 'placeholder'
        llm_api_key: 'somethingelse'
      ollama_llm:
        base_url: 'http://localhost:11434/v1'
        model: 'qwen2.5:3b'
      lmstudio_llm:
        base_url: 'http://localhost:1234/v1'
        model: 'qwen2.5:3b'
"""


@pytest.fixture(autouse=True)
def conf_file(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(conf_editor, "CONF_PATH", str(path))
    monkeypatch.setattr(route, "CONF_PATH", str(path), raising=False)
    return path


def _read(path):
    return path.read_text(encoding="utf-8")


def test_writes_into_the_named_block(conf_file):
    route.write_provider_config(
        "lmstudio_llm", {"base_url": "http://127.0.0.1:1234/v1", "model": "qwen/qwen3.5-9b"}
    )
    text = _read(conf_file)
    assert "model: 'qwen/qwen3.5-9b'" in text
    # ollama 那塊不能被波及
    assert "model: 'qwen2.5:3b'" in text


def test_points_llm_provider_at_that_block(conf_file):
    route.write_provider_config("lmstudio_llm", {"model": "m"})
    assert "llm_provider: 'lmstudio_llm'" in _read(conf_file)


def test_writes_extra_body(conf_file):
    route.write_provider_config(
        "lmstudio_llm", {"model": "m", "extra_body": {"reasoning_effort": "none"}}
    )
    text = _read(conf_file)
    assert "extra_body:" in text
    assert "reasoning_effort: 'none'" in text


def test_omitted_keys_are_left_alone(conf_file):
    """只給 model 就只改 model，base_url 維持原樣。"""
    route.write_provider_config("lmstudio_llm", {"model": "m"})
    text = _read(conf_file)
    assert "base_url: 'http://localhost:1234/v1'" in text


def test_unknown_provider_is_rejected(conf_file):
    with pytest.raises(ValueError):
        route.write_provider_config("../../etc/passwd", {"model": "m"})


def test_missing_block_raises(conf_file):
    """provider 在白名單內（不是「未知供應商」），但這份 conf.yaml 裡沒有
    ollama_llm 這個區塊——nested_extent 沿路徑鑽到最後一層才找不到，丟
    KeyError。跟 test_unknown_provider_is_rejected 的 ValueError 是不同的
    失敗模式：前者是「這個字串根本不在白名單」，後者是「白名單內的供應商，
    但這台機器的 conf.yaml 沒寫那個區塊」。

    偏離 brief 原文：brief 這裡原本傳的是 "claude_llm"，但 claude_llm 不在
    WRITABLE_PROVIDERS 白名單裡，會先被 ValueError 擋下，不會走到
    nested_extent，測不到這裡真正要測的東西。細節見 task-3-report.md。
    """
    conf_file.write_text(
        "character_config:\n"
        "  agent_config:\n"
        "    agent_settings:\n"
        "      basic_memory_agent:\n"
        "        llm_provider: 'openai_compatible_llm'\n"
        "    llm_configs:\n"
        "      openai_compatible_llm:\n"
        "        base_url: 'http://localhost:11434/v1'\n"
        "        model: 'placeholder'\n"
        "        llm_api_key: 'somethingelse'\n",
        encoding="utf-8",
    )
    with pytest.raises(KeyError):
        route.write_provider_config("ollama_llm", {"model": "m"})


def test_write_openai_block_inserts_missing_leaf_instead_of_raising(conf_file):
    """刻意跟重構前的 rewrite_str_leaf 行為不同,不是沒注意到的迴歸。

    舊版 _write_openai_block 用 rewrite_str_leaf 逐一改寫 base_url／model／
    llm_api_key,任何一個在區塊裡找不到就丟 KeyError("Could not locate keys
    [...]")。重構後 _write_openai_block 委派給 write_provider_config,走的是
    upsert_leaf,找不到的葉節點會被插入,不丟例外。

    這是刻意保留新行為,不是要修回去:upsert_leaf 自己的 docstring 講得很清楚
    ——UI 開得出來的設定就該存得下去,手寫的 conf.yaml 常常根本沒有那一行,
    舊版在這種情況直接丟 KeyError、畫面顯示「無法寫入設定檔」,而使用者只是
    想存一個他有權存的值,這是舊版自己的 bug,不是這裡要保留的行為。
    """
    conf_file.write_text(
        "character_config:\n"
        "  agent_config:\n"
        "    agent_settings:\n"
        "      basic_memory_agent:\n"
        "        llm_provider: 'openai_compatible_llm'\n"
        "    llm_configs:\n"
        "      openai_compatible_llm:\n"
        "        base_url: 'http://localhost:11434/v1'\n"
        "        model: 'placeholder'\n",
        encoding="utf-8",
    )
    # 這個區塊沒有 llm_api_key 這一行——重點是這裡不能丟例外。
    route._write_openai_block("http://127.0.0.1:1234/v1", "new-model", "sk-secret")

    text = _read(conf_file)
    assert "llm_api_key: 'sk-secret'" in text
    assert "base_url: 'http://127.0.0.1:1234/v1'" in text
    assert "model: 'new-model'" in text
