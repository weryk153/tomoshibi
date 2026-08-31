"""把 LM Studio 的模型清單正規化成 DetectedModel。

這層只做翻譯：問到什麼、轉成什麼。不決定任何設定、不寫任何檔案——設定的決定
在 model_profiles，寫入在 write_provider_config。

測試餵假 payload，不打網路。真實形狀取自開發機（LM Studio 0.3.x）：
  {"id","object","type","publisher","arch","compatibility_type","quantization",
   "state","max_context_length","capabilities"}
"""

import pytest

from src.open_llm_vtuber import model_probe, context_window

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
    """連不上不能讓 list_lmstudio_models 往外丟例外——它的呼叫端（例如
    apply-detected 要重新核對模型是否還在）不在乎可不可達，只要一份清單。

    「連不上」跟「可達但沒模型」曾經被這個函式的空清單結果混成同一件事；那個
    區分現在在 probe_lmstudio()（見下面兩條測試），這裡只驗證 list_* 這層
    薄包裝不會把底層的例外洩漏出去。
    """

    def boom(base_url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(model_probe, "fetch_lmstudio_models", boom)
    assert model_probe.list_lmstudio_models(BASE) == []


def test_probe_distinguishes_unreachable_from_reachable_but_empty(monkeypatch, fake_fetch):
    """probe_lmstudio() 的重點：連不上 vs 連得上但零模型，是兩種不同的
    (reachable, models) 組合，不能只看 models 是不是空清單去猜 reachable。
    """

    def boom(base_url):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(model_probe, "fetch_lmstudio_models", boom)
    reachable, models = model_probe.probe_lmstudio(BASE)
    assert reachable is False
    assert models == []

    fake_fetch({"data": []})
    reachable, models = model_probe.probe_lmstudio(BASE)
    assert reachable is True, "連得上但一顆模型都沒下載，仍然是可達的"
    assert models == []


def test_probe_reachable_with_models(fake_fetch):
    fake_fetch(PAYLOAD)
    reachable, models = model_probe.probe_lmstudio(BASE)
    assert reachable is True
    assert len(models) == 2


def test_garbage_entries_are_skipped(fake_fetch):
    fake_fetch({"data": ["not a dict", {"type": "llm"}, {"id": "ok", "type": "llm"}]})
    ids = [m.id for m in model_probe.list_lmstudio_models(BASE)]
    assert ids == ["ok"], "沒有 id 的項目要丟掉"


def test_context_window_uses_its_own_timeout(monkeypatch):
    """context_window._probe_lmstudio 要用 1.5s 而不是 model_probe 的 3.0s 預設。

    對話中途的探測要快速失敗（同步在事件迴圈），設定期的 list_lmstudio_models
    則使用者願意等。
    """
    # 先清快取
    context_window.reset_cache()

    captured_args = []

    def capture_fetch(base_url, timeout=3.0):
        """Mock fetch_lmstudio_models，記錄收到的 timeout 引數。"""
        captured_args.append({"timeout": timeout})
        # 回傳一個有 loaded_context_length 的假模型
        return [{"id": "test-model-unique", "loaded_context_length": 8192}]

    # Monkeypatch context_window 的 fetch_lmstudio_models
    # （它是從 model_probe import 過來的，但要在 context_window namespace 改）
    monkeypatch.setattr(context_window, "fetch_lmstudio_models", capture_fetch)

    # 呼叫 context_window 的探測
    result = context_window._probe_lmstudio("http://unique.test:1234/v1", None)

    # 驗證回傳值
    assert result == 8192

    # 驗證 timeout 確實是 1.5s（_PROBE_TIMEOUT），不是 3.0s（model_probe._TIMEOUT）
    assert len(captured_args) == 1
    assert captured_args[0]["timeout"] == context_window._PROBE_TIMEOUT
    assert captured_args[0]["timeout"] == 1.5

    # 清理快取
    context_window.reset_cache()
