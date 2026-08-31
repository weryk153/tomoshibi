"""問推論端 window 多大：探測層的行為契約。

重點不是「會發 HTTP」，而是失敗時的樣子——這條路徑在對話中途被呼叫，任何一種
問不到都必須安靜地回 None 讓呼叫端退回保守預設，絕不能丟例外。

還有一條容易寫錯的：模型「還沒載入」跟「端點不存在」要分開處理。LM Studio 預設
JIT 載入，開機時問一定是前者，那時快取住 None 會讓後面永遠問不到。
"""

import pytest

from src.open_llm_vtuber import context_window as cw


@pytest.fixture(autouse=True)
def _clean():
    cw.reset_cache()
    yield
    cw.reset_cache()


def _stub(monkeypatch, fn):
    monkeypatch.setattr(cw, "_probe_lmstudio", fn)


def test_returns_detected_window(monkeypatch):
    _stub(monkeypatch, lambda base_url, model: 20992)
    assert cw.detect_context_window("http://x:1234/v1", "m") == 20992


def test_result_is_cached(monkeypatch):
    calls = []
    _stub(monkeypatch, lambda base_url, model: calls.append(1) or 20992)
    cw.detect_context_window("http://x:1234/v1")
    cw.detect_context_window("http://x:1234/v1")
    assert len(calls) == 1


def test_probe_failure_is_silent():
    """沒有東西在聽時不能炸——這條在對話路徑上。"""
    assert cw.detect_context_window("http://127.0.0.1:9/v1") is None


def test_exceptions_never_escape(monkeypatch):
    def boom(base_url, model):
        raise RuntimeError("推論端壞掉了")

    _stub(monkeypatch, boom)
    assert cw.detect_context_window("http://x:1234/v1") is None


def test_no_base_url_means_no_probe():
    assert cw.detect_context_window("") is None


def test_not_loaded_yet_is_retried_later(monkeypatch):
    """模型還沒載入只是「現在還不知道」，不是「永遠不知道」。

    LM Studio 是 JIT 載入的，第一次問常常撲空。把 None 快取起來會讓它永遠
    退回保守預設，即使模型早就載好了。
    """
    answers = [None, 20992]
    _stub(monkeypatch, lambda base_url, model: answers.pop(0))

    assert cw.detect_context_window("http://x:1234/v1") is None
    monkeypatch.setattr(cw, "_RETRY_COOLDOWN", 0)  # 快轉冷卻
    assert cw.detect_context_window("http://x:1234/v1") == 20992


def test_failures_are_rate_limited(monkeypatch):
    """撲空之後不該每則訊息都重問一次——探測是同步的。"""
    calls = []
    _stub(monkeypatch, lambda base_url, model: calls.append(1) or None)
    for _ in range(5):
        cw.detect_context_window("http://x:1234/v1")
    assert len(calls) == 1


def test_lmstudio_root_strips_the_openai_suffix():
    """設定裡是 /v1，而 /api/v0 跟它平行，不是它底下。"""
    assert cw._lmstudio_root("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234"
    assert cw._lmstudio_root("http://127.0.0.1:1234/v1/") == "http://127.0.0.1:1234"
    assert cw._lmstudio_root("http://127.0.0.1:1234") == "http://127.0.0.1:1234"
