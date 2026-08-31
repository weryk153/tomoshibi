"""機器的實體記憶體總量。

只有一個用途：決定首次啟動精靈建議下載哪顆模型。測不到就回 None，呼叫端會用
fallback——這條路徑絕不能因為抓不到硬體資訊就壞掉。
"""

from src.open_llm_vtuber import system_probe


def test_returns_a_plausible_number():
    ram = system_probe.total_ram_bytes()
    assert ram is None or ram > 512 * 1024**2, "小於 512MB 不像是真的"


def test_failure_returns_none(monkeypatch):
    """psutil 在某些受限環境會丟例外。不得往上炸。"""

    class _Boom:
        @staticmethod
        def virtual_memory():
            raise RuntimeError("no /proc here")

    monkeypatch.setattr(system_probe, "psutil", _Boom)
    assert system_probe.total_ram_bytes() is None


def test_zero_is_treated_as_unknown(monkeypatch):
    """0 不是一個有意義的答案，當成測不到。"""

    class _Zero:
        @staticmethod
        def virtual_memory():
            class _V:
                total = 0

            return _V()

    monkeypatch.setattr(system_probe, "psutil", _Zero)
    assert system_probe.total_ram_bytes() is None
