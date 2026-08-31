"""Ollama 的模型清單與細節。

分兩階段是刻意的：/api/show 要逐顆呼叫，使用者有 20 顆模型就是 20 次請求。
列表時只列（/api/tags 一次拿完），選定後才問細節。

LM Studio 一次全拿沒這問題，但兩邊的介面刻意長得一樣，讓路由層不必分兩套寫。
"""

from src.open_llm_vtuber import model_probe

BASE = "http://localhost:11434/v1"

TAGS = {
    "models": [
        {"name": "qwen3:8b", "details": {"family": "qwen3"}},
        {"name": "llama3.2-vision:11b", "details": {"family": "mllama"}},
    ]
}

SHOW_VISION_TOOLS = {
    "details": {"family": "mllama", "quantization_level": "Q4_K_M"},
    "capabilities": ["completion", "vision", "tools"],
    "model_info": {"mllama.context_length": 131072},
}

SHOW_PLAIN = {
    "details": {"family": "qwen3", "quantization_level": "Q4_K_M"},
    "capabilities": ["completion"],
    "model_info": {"qwen3.context_length": 40960},
}


def test_list_returns_ids_without_capabilities(monkeypatch):
    monkeypatch.setattr(
        model_probe, "fetch_ollama_tags", lambda base_url: TAGS["models"]
    )
    models = model_probe.list_ollama_models(BASE)
    assert [m.id for m in models] == ["qwen3:8b", "llama3.2-vision:11b"]
    assert all(m.backend == "ollama" for m in models)
    # 列表階段還沒問細節，能力欄位維持預設
    assert all(m.is_vlm is False and m.supports_tools is False for m in models)


def test_describe_fills_in_capabilities(monkeypatch):
    monkeypatch.setattr(
        model_probe, "fetch_ollama_show", lambda base_url, model_id: SHOW_VISION_TOOLS
    )
    m = model_probe.describe_ollama_model(BASE, "llama3.2-vision:11b")
    assert m.arch == "mllama"
    assert m.is_vlm is True
    assert m.supports_tools is True
    assert m.max_context == 131072
    assert m.quantization == "Q4_K_M"


def test_describe_plain_model(monkeypatch):
    monkeypatch.setattr(
        model_probe, "fetch_ollama_show", lambda base_url, model_id: SHOW_PLAIN
    )
    m = model_probe.describe_ollama_model(BASE, "qwen3:8b")
    assert m.is_vlm is False
    assert m.supports_tools is False
    assert m.max_context == 40960


def test_context_length_key_is_arch_prefixed(monkeypatch):
    """model_info 的 context 鍵是 '<arch>.context_length'，不是固定名字。
    只認固定名字的話換個模型家族就抓不到。"""
    payload = {
        "details": {"family": "gemma3"},
        "capabilities": ["completion"],
        "model_info": {"gemma3.context_length": 8192, "general.parameter_count": 4},
    }
    monkeypatch.setattr(model_probe, "fetch_ollama_show", lambda b, m: payload)
    assert model_probe.describe_ollama_model(BASE, "gemma3:4b").max_context == 8192


def test_list_failure_returns_empty(monkeypatch):
    def boom(base_url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(model_probe, "fetch_ollama_tags", boom)
    assert model_probe.list_ollama_models(BASE) == []


def test_probe_distinguishes_unreachable_from_reachable_but_empty(monkeypatch):
    """probe_ollama() 的重點：連不上 vs 連得上但零模型是兩種不同的
    (reachable, models) 組合——理由同 test_model_probe_lmstudio.py 那條
    對稱測試。"""

    def boom(base_url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(model_probe, "fetch_ollama_tags", boom)
    reachable, models = model_probe.probe_ollama(BASE)
    assert reachable is False
    assert models == []

    monkeypatch.setattr(model_probe, "fetch_ollama_tags", lambda base_url: [])
    reachable, models = model_probe.probe_ollama(BASE)
    assert reachable is True, "daemon 連得上但還沒 pull 任何模型，仍然是可達的"
    assert models == []


def test_probe_reachable_with_models(monkeypatch):
    monkeypatch.setattr(
        model_probe, "fetch_ollama_tags", lambda base_url: TAGS["models"]
    )
    reachable, models = model_probe.probe_ollama(BASE)
    assert reachable is True
    assert len(models) == 2


def test_describe_failure_returns_none(monkeypatch):
    def boom(base_url, model_id):
        raise RuntimeError("nope")

    monkeypatch.setattr(model_probe, "fetch_ollama_show", boom)
    assert model_probe.describe_ollama_model(BASE, "x") is None
