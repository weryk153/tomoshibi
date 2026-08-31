"""把 LM Studio 的模型清單正規化成 DetectedModel。

這層只做翻譯：問到什麼、轉成什麼。不決定任何設定、不寫任何檔案——設定的決定
在 model_profiles，寫入在 write_provider_config。

測試餵假 payload，不打網路。真實形狀取自開發機（LM Studio 0.3.x）：
  {"id","object","type","publisher","arch","compatibility_type","quantization",
   "state","max_context_length","capabilities"}
"""

import pytest

from src.open_llm_vtuber import model_probe

PAYLOAD = {
    "data": [
        {
            "id": "qwen/qwen3.5-9b",
            "type": "vlm",
            "arch": "qwen35",
            "compatibility_type": "mlx",
            "quantization": "4bit",
            "state": "loaded",
            "max_context_length": 262144,
            "capabilities": ["tool_use"],
        },
        {
            "id": "defiant-fable-9b",
            "type": "llm",
            "arch": "qwen35",
            "compatibility_type": "gguf",
            "quantization": "Q4_K_M",
            "state": "not-loaded",
            "max_context_length": 262144,
        },
        {
            "id": "text-embedding-nomic-embed-text-v1",
            "type": "embeddings",
            "arch": "nomic-bert",
            "state": "not-loaded",
            "max_context_length": 2048,
        },
    ]
}

BASE = "http://127.0.0.1:1234/v1"


@pytest.fixture
def fake_fetch(monkeypatch):
    def _install(payload):
        monkeypatch.setattr(
            model_probe, "fetch_lmstudio_models", lambda base_url: payload["data"]
        )

    return _install


def test_normalizes_a_vlm_with_tools(fake_fetch):
    fake_fetch(PAYLOAD)
    models = {m.id: m for m in model_probe.list_lmstudio_models(BASE)}
    m = models["qwen/qwen3.5-9b"]
    assert m.backend == "lmstudio"
    assert m.base_url == BASE
    assert m.arch == "qwen35"
    assert m.is_vlm is True
    assert m.supports_tools is True
    assert m.max_context == 262144
    assert m.quantization == "4bit"


def test_plain_llm_is_not_a_vlm(fake_fetch):
    fake_fetch(PAYLOAD)
    models = {m.id: m for m in model_probe.list_lmstudio_models(BASE)}
    m = models["defiant-fable-9b"]
    assert m.is_vlm is False
    assert m.supports_tools is False, "沒有 capabilities 欄位要當成不支援"


def test_embedding_models_are_excluded(fake_fetch):
    """嵌入模型不能拿來對話，列出來只會讓使用者選錯。"""
    fake_fetch(PAYLOAD)
    ids = [m.id for m in model_probe.list_lmstudio_models(BASE)]
    assert "text-embedding-nomic-embed-text-v1" not in ids
    assert len(ids) == 2


def test_missing_fields_do_not_crash(fake_fetch):
    fake_fetch({"data": [{"id": "bare-model", "type": "llm"}]})
    (m,) = model_probe.list_lmstudio_models(BASE)
    assert m.id == "bare-model"
    assert m.arch is None
    assert m.max_context is None
    assert m.is_vlm is False


def test_probe_failure_returns_empty_list(monkeypatch):
    """連不上不是錯誤，是「這個後端現在沒有模型」。不得丟例外。"""

    def boom(base_url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(model_probe, "fetch_lmstudio_models", boom)
    assert model_probe.list_lmstudio_models(BASE) == []


def test_garbage_entries_are_skipped(fake_fetch):
    fake_fetch({"data": ["not a dict", {"type": "llm"}, {"id": "ok", "type": "llm"}]})
    ids = [m.id for m in model_probe.list_lmstudio_models(BASE)]
    assert ids == ["ok"], "沒有 id 的項目要丟掉"
