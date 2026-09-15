"""整理一次呼叫，兩份記憶分別落地。

- 兩段都有才落地；缺任一段標記兩份都不寫。
- self 段先過 filter_self_lines 再寫。
- 每一份各自套 _acceptable_rewrite（空／沒變／超過 1.5 倍上限 → 那一份不動）。
- 鎖以 conf_uid 為單位：同角色兩段對話同時整理，兩邊的新條目都要保留。
"""

import asyncio

import pytest

from src.open_llm_vtuber import memory_core
from src.open_llm_vtuber.memory_core import (
    SECTION_CONVERSATION,
    SELF_CAP_CHARS,
    load_core_memory,
    load_self_memory,
    save_core_memory,
    save_self_memory,
    self_section_label,
)

CONF = "consol-test"
NAME = "紅莉栖"
LABEL = self_section_label(NAME)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_core._consolidation_locks.clear()


def _run(history_uid, reply, monkeypatch):
    async def fake_rewrite(base_url, model, prompt, api_key, extra_body):
        return reply

    monkeypatch.setattr(memory_core, "_request_rewrite", fake_rewrite)
    asyncio.run(
        memory_core.consolidate_core_memory(
            CONF,
            history_uid,
            "說了些話",
            "回了些話",
            base_url="http://stub",
            model="stub",
            character_name=NAME,
        )
    )


def test_writes_both_sections_to_their_own_files(monkeypatch):
    _run(
        "conv-1",
        f"{SECTION_CONVERSATION}\n對方叫小明。\n{LABEL}\n紅莉栖喜歡咖啡。",
        monkeypatch,
    )
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"
    assert load_self_memory(CONF) == "紅莉栖喜歡咖啡。"


def test_missing_marker_writes_nothing(monkeypatch):
    save_core_memory(CONF, "conv-1", "原本的")
    save_self_memory(CONF, "原本她的")
    _run("conv-1", "對方叫小明。\n紅莉栖喜歡咖啡。", monkeypatch)
    assert load_core_memory(CONF, "conv-1") == "原本的"
    assert load_self_memory(CONF) == "原本她的"


def test_self_lines_mentioning_the_other_party_are_dropped(monkeypatch):
    _run(
        "conv-1",
        f"{SECTION_CONVERSATION}\n對方叫小明。\n{LABEL}\n紅莉栖喜歡咖啡。\n紅莉栖和對方去過秋葉原。",
        monkeypatch,
    )
    assert load_self_memory(CONF) == "紅莉栖喜歡咖啡。"


def test_unchanged_self_section_does_not_rewrite_self_file(monkeypatch, tmp_path):
    save_self_memory(CONF, "紅莉栖喜歡咖啡。")
    before = (tmp_path / "chat_history" / CONF / "self_memory.md").stat().st_mtime_ns
    _run(
        "conv-1",
        f"{SECTION_CONVERSATION}\n對方叫小明。\n{LABEL}\n紅莉栖喜歡咖啡。",
        monkeypatch,
    )
    after = (tmp_path / "chat_history" / CONF / "self_memory.md").stat().st_mtime_ns
    assert before == after
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"


def test_oversized_self_section_is_rejected_but_conversation_still_lands(monkeypatch):
    huge = "紅莉栖喜歡" + "咖" * (int(SELF_CAP_CHARS * 1.5) + 10)
    _run(
        "conv-1", f"{SECTION_CONVERSATION}\n對方叫小明。\n{LABEL}\n{huge}", monkeypatch
    )
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"
    assert load_self_memory(CONF) == ""


def test_placeholder_echoed_by_llm_does_not_write_self_memory(monkeypatch, tmp_path):
    """Round-1 fix regression: the model echoing the '現有' placeholder back must
    not land in self_memory.md (finding A)."""
    _run(
        "conv-1",
        f"{SECTION_CONVERSATION}\n對方叫小明。\n{LABEL}\n（目前還沒有任何關於自己的記憶）",
        monkeypatch,
    )
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"
    assert load_self_memory(CONF) == ""
    assert not (tmp_path / "chat_history" / CONF / "self_memory.md").exists()


def test_self_memory_is_shared_across_conversations(monkeypatch):
    _run(
        "conv-a",
        f"{SECTION_CONVERSATION}\n對方叫小明。\n{LABEL}\n紅莉栖喜歡咖啡。",
        monkeypatch,
    )
    _run(
        "conv-b",
        f"{SECTION_CONVERSATION}\n對方叫小華。\n{LABEL}\n紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。",
        monkeypatch,
    )
    assert load_core_memory(CONF, "conv-a") == "對方叫小明。"
    assert load_core_memory(CONF, "conv-b") == "對方叫小華。"
    assert load_self_memory(CONF) == "紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。"


def test_prompt_receives_the_existing_self_memory(monkeypatch):
    save_self_memory(CONF, "紅莉栖喜歡咖啡。")
    seen = {}

    async def fake_rewrite(base_url, model, prompt, api_key, extra_body):
        seen["prompt"] = prompt
        return ""

    monkeypatch.setattr(memory_core, "_request_rewrite", fake_rewrite)
    asyncio.run(
        memory_core.consolidate_core_memory(
            CONF,
            "conv-1",
            "x",
            "y",
            base_url="http://stub",
            model="stub",
            character_name=NAME,
        )
    )
    assert "紅莉栖喜歡咖啡。" in seen["prompt"]


def test_two_conversations_of_one_character_queue_and_keep_both_self_entries(
    monkeypatch,
):
    """沒有角色層的鎖時，兩邊各自從空白的 self_memory 長出來、後寫的整份蓋掉先寫的。"""

    async def fake_rewrite(base_url, model, prompt, api_key, extra_body):
        await asyncio.sleep(0.05)
        existing_has_a = "紅莉栖喜歡咖啡。" in prompt
        conv = "對方甲" if "甲說的" in prompt else "對方乙"
        self_lines = (
            ["紅莉栖喜歡咖啡。"]
            if not existing_has_a
            else ["紅莉栖喜歡咖啡。", "紅莉栖討厭夏天。"]
        )
        return f"{SECTION_CONVERSATION}\n{conv}\n{LABEL}\n" + "\n".join(self_lines)

    monkeypatch.setattr(memory_core, "_request_rewrite", fake_rewrite)

    async def _both():
        await asyncio.gather(
            memory_core.consolidate_core_memory(
                CONF,
                "conv-a",
                "甲說的",
                "回甲",
                base_url="http://stub",
                model="stub",
                character_name=NAME,
            ),
            memory_core.consolidate_core_memory(
                CONF,
                "conv-b",
                "乙說的",
                "回乙",
                base_url="http://stub",
                model="stub",
                character_name=NAME,
            ),
        )

    asyncio.run(_both())
    stored = load_self_memory(CONF)
    assert "紅莉栖喜歡咖啡。" in stored
    assert "紅莉栖討厭夏天。" in stored


def test_different_characters_do_not_wait_for_each_other(monkeypatch):
    in_flight = 0
    peak = 0

    async def fake_rewrite(base_url, model, prompt, api_key, extra_body):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return f"{SECTION_CONVERSATION}\n對方x\n{self_section_label('')}\n角色y"

    monkeypatch.setattr(memory_core, "_request_rewrite", fake_rewrite)

    async def _both():
        await asyncio.gather(
            memory_core.consolidate_core_memory(
                "char-a", "c", "a", "b", base_url="http://stub", model="stub"
            ),
            memory_core.consolidate_core_memory(
                "char-b", "c", "a", "b", base_url="http://stub", model="stub"
            ),
        )

    asyncio.run(_both())
    assert peak == 2
