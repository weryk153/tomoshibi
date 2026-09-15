"""整理不能兩份同時跑：同一個角色的整理必須排隊。

釘住的行為契約：整理是「讀出整份記憶 → 丟給 LLM 重寫 → 整份覆寫」，中間那步
會花到 60 秒。沒有鎖的話第 N 輪還在等 LLM、第 N+1 輪就開始，兩邊各自讀到同一份
舊記憶當底稿、各自整份寫回，後寫的贏——先寫那輪的新事實靜默消失。

鎖改成以角色為單位，因為 self_memory.md 是同角色所有對話共用的：兩段對話同時
整理，若各鎖各的對話，仍會各自讀到同一份舊的 self 記憶當底稿、整份寫回，
後寫的蓋掉先寫的新條目。

這裡不去斷言「有一把 asyncio.Lock」（那是實作），而是斷言後來者看得見前一輪的
結果，也就是併發保護真正要買的東西。
"""

import asyncio

import pytest

from src.open_llm_vtuber import memory_core

CONF = "lock-test"
HISTORY = "conv-1"


@pytest.fixture(autouse=True)
def _isolated_chat_history(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_core._consolidation_locks.clear()


def _consolidate(user_input, ai_response):
    return memory_core.consolidate_core_memory(
        CONF,
        HISTORY,
        user_input,
        ai_response,
        base_url="http://stub",
        model="stub",
        character_name="角色",
    )


def test_overlapping_consolidations_do_not_clobber_each_other(monkeypatch):
    """第二輪必須讀到第一輪寫下的記憶，而不是兩邊都從空白長出來。"""
    seen_current = []
    tail = "\n【角色自己】\n"

    async def fake_rewrite(base_url, model, prompt, api_key, extra_body):
        # 提示詞裡帶著「現有記憶」，用它反推這一輪讀到的底稿是什麼。
        seen_current.append("第一輪的事實" in prompt)
        await asyncio.sleep(0.05)  # 模擬 LLM 的往返
        if "第一輪的事實" in prompt:
            return "【對話記憶】\n第一輪的事實\n第二輪的事實" + tail
        return "【對話記憶】\n第一輪的事實" + tail

    monkeypatch.setattr(memory_core, "_request_rewrite", fake_rewrite)

    async def _both():
        await asyncio.gather(
            _consolidate("先講的", "回一"),
            _consolidate("後講的", "回二"),
        )

    asyncio.run(_both())

    # 沒有鎖時兩輪都讀到空白（seen_current == [False, False]），最終檔案只剩
    # 一條，先寫那輪的事實消失。有鎖時後來者看得見前一輪。
    assert seen_current == [False, True]
    stored = memory_core.load_core_memory(CONF, HISTORY)
    assert "第一輪的事實" in stored
    assert "第二輪的事實" in stored


def test_lock_table_evicts_only_unheld_locks():
    """鎖表不能無限長，但正在用的鎖丟不得——丟掉等於併發保護破功。"""
    memory_core._consolidation_locks.clear()
    held = memory_core._consolidation_lock("held")

    async def _hold():
        async with held:
            for i in range(memory_core._MAX_LOCKS + 10):
                memory_core._consolidation_lock(f"char-{i}")
            assert len(memory_core._consolidation_locks) <= memory_core._MAX_LOCKS + 1
            assert "held" in memory_core._consolidation_locks

    asyncio.run(_hold())
