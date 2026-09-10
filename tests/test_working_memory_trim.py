"""短期記憶（self._memory）的上限。

背景：這份記憶原本沒有任何上限——set_memory_from_history 把整段對話全載進來，
_add_message 一路往後加。長對話遲早撐爆模型的 context window，本地小模型（8k）
會先爆，而症狀是回覆變糊或忘記剛講過的話，不是一個清楚的錯誤。

這裡釘的是截斷的行為契約，不是某個數字：
- 平常聊天不該被截（底線以內原封不動）。
- 撞到預算才截，而且從最舊的開始。
- 底線贏預算：再長也留得下最近幾輪，不會被砍到接不上話。
- 截完開頭必須是 user，否則模型讀到的第一件事是自己的話。
- 兩個入口都要擋：一則一則長出來的 _add_message，和一次全灌的
  set_memory_from_history。
"""

import pytest

from src.open_llm_vtuber.agent.agents import basic_memory_agent as bma
from src.open_llm_vtuber.agent.agents.basic_memory_agent import (
    MEMORY_MAX_CHARS,
    MEMORY_MIN_MESSAGES,
    MIN_BUDGET_CHARS,
    BasicMemoryAgent,
)


def _agent(system=""):
    """只取記憶那一塊，不碰 LLM／TTS／Live2D。"""
    agent = BasicMemoryAgent.__new__(BasicMemoryAgent)
    agent._memory = []
    agent._system = system
    agent._llm_base_url = "http://stub:1234/v1"
    agent._llm_model = "stub-model"
    return agent


@pytest.fixture(autouse=True)
def _no_real_probe(monkeypatch):
    """預設當作問不到 window——測試絕不對外發請求。"""
    monkeypatch.setattr(bma, "detect_context_window", lambda *a, **k: None)


def _fill(agent, pairs, chars_each):
    for i in range(pairs):
        agent._memory.append({"role": "user", "content": f"u{i}" + "字" * chars_each})
        agent._memory.append(
            {"role": "assistant", "content": f"a{i}" + "字" * chars_each}
        )


def test_short_conversation_is_left_alone():
    agent = _agent()
    _fill(agent, pairs=5, chars_each=10)
    before = list(agent._memory)
    agent._trim_memory()
    assert agent._memory == before


def test_over_budget_drops_oldest_first():
    agent = _agent()
    # 每則 2000 字、40 則 = 80,000 字，遠超 12,000 的預算。
    _fill(agent, pairs=20, chars_each=2000)
    agent._trim_memory()

    total = sum(len(m["content"]) for m in agent._memory)
    assert total <= MEMORY_MAX_CHARS or len(agent._memory) <= MEMORY_MIN_MESSAGES
    # 留下的是最後那幾輪，不是最前面那幾輪。
    assert agent._memory[-1]["content"].startswith("a19")
    assert not any(m["content"].startswith("u0") for m in agent._memory)


def test_floor_wins_over_budget():
    """每則都超長時，預算會想砍到見底；底線必須擋住。"""
    agent = _agent()
    _fill(agent, pairs=30, chars_each=MEMORY_MAX_CHARS)
    agent._trim_memory()
    # 底線是 MEMORY_MIN_MESSAGES，對齊 user 開頭最多再少一則。
    assert len(agent._memory) >= MEMORY_MIN_MESSAGES - 1


def test_trimmed_memory_starts_with_user():
    agent = _agent()
    _fill(agent, pairs=20, chars_each=2000)
    agent._trim_memory()
    assert agent._memory[0]["role"] == "user"


def test_add_message_keeps_memory_bounded():
    """一則一則長出來的路徑也要被擋住。"""
    agent = _agent()
    for i in range(200):
        agent._memory.append({"role": "user", "content": "字" * 500})
        agent._trim_memory()
        agent._memory.append({"role": "assistant", "content": "字" * 500})
        agent._trim_memory()

    total = sum(len(m["content"]) for m in agent._memory)
    assert total <= MEMORY_MAX_CHARS + 500, "記憶沒有被壓在預算附近"
    assert len(agent._memory) >= MEMORY_MIN_MESSAGES - 1


# --- 依實際 window 調整預算 ---------------------------------------------------


def test_budget_falls_back_when_window_unknown():
    """問不到就用保守預設，不能因為問不到就不設限。"""
    assert _agent()._memory_budget_chars() == MEMORY_MAX_CHARS


def test_big_window_widens_the_budget(monkeypatch):
    """20,992 的 window 配 長人設等級的 system prompt，應該比保守預設寬。"""
    monkeypatch.setattr(bma, "detect_context_window", lambda *a, **k: 20992)
    agent = _agent(system="人" * 5000)  # 約 3,200 token 的 system prompt
    assert agent._memory_budget_chars() > MEMORY_MAX_CHARS


def test_small_window_tightens_below_the_default(monkeypatch):
    """window 只有 4k 時必須勒緊——這才是去問的理由。"""
    monkeypatch.setattr(bma, "detect_context_window", lambda *a, **k: 4096)
    agent = _agent(system="人" * 3000)
    assert agent._memory_budget_chars() < MEMORY_MAX_CHARS


def test_budget_never_collapses_to_nothing(monkeypatch):
    """system prompt 撐爆整個 window 時仍要留下能講話的地板。"""
    monkeypatch.setattr(bma, "detect_context_window", lambda *a, **k: 2048)
    agent = _agent(system="人" * 100000)
    assert agent._memory_budget_chars() == MIN_BUDGET_CHARS


def test_normal_conversation_never_probes(monkeypatch):
    """保守預算以內連問都不該問——探測是同步的，不能每則訊息都發請求。"""
    calls = []
    monkeypatch.setattr(
        bma, "detect_context_window", lambda *a, **k: calls.append(1) or 20992
    )
    agent = _agent()
    _fill(agent, pairs=100, chars_each=30)  # 6,000 字元，遠在 20,000 之內
    agent._trim_memory()
    assert calls == [], "沒超過保守預算就去探測了"
