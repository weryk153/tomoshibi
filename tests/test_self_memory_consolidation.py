"""整理一次呼叫，兩份記憶分別落地——分類由程式做（classify_memory_lines）。

- 模型只回一份清單；程式逐行分類成對話記憶／她自己的，各自落地。
- 每一份各自套 _acceptable_rewrite（空／沒變／超過 1.5 倍上限 → 那一份不動）。
- 鎖以 conf_uid 為單位：同角色兩段對話同時整理，兩邊的新條目都要保留。
"""

import asyncio

import pytest

from src.open_llm_vtuber import memory_core
from src.open_llm_vtuber.memory_core import (
    SELF_CAP_CHARS,
    load_core_memory,
    load_self_memory,
    save_core_memory,
    save_self_memory,
)

CONF = "consol-test"
NAME = "紅莉栖"


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    memory_core._consolidation_locks.clear()


def _run(
    history_uid,
    reply,
    monkeypatch,
    character_name=NAME,
    reply_language="",
    protected_names=None,
):
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
            character_name=character_name,
            reply_language=reply_language,
            protected_names=protected_names,
        )
    )


def test_writes_both_sections_to_their_own_files(monkeypatch):
    _run("conv-1", "對方叫小明。\n紅莉栖喜歡咖啡。", monkeypatch)
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"
    assert load_self_memory(CONF) == "紅莉栖喜歡咖啡。"


def test_self_lines_mentioning_the_other_party_land_in_conversation_not_self(
    monkeypatch,
):
    _run(
        "conv-1",
        "對方叫小明。\n紅莉栖喜歡咖啡。\n紅莉栖和對方去過秋葉原。",
        monkeypatch,
    )
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。\n紅莉栖和對方去過秋葉原。"
    assert load_self_memory(CONF) == "紅莉栖喜歡咖啡。"


def test_unchanged_self_section_does_not_rewrite_self_file(monkeypatch, tmp_path):
    save_self_memory(CONF, "紅莉栖喜歡咖啡。")
    before = (tmp_path / "chat_history" / CONF / "self_memory.md").stat().st_mtime_ns
    _run("conv-1", "對方叫小明。\n紅莉栖喜歡咖啡。", monkeypatch)
    after = (tmp_path / "chat_history" / CONF / "self_memory.md").stat().st_mtime_ns
    assert before == after
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"


def test_oversized_self_section_is_rejected_but_conversation_still_lands(monkeypatch):
    huge = "紅莉栖喜歡" + "咖" * (int(SELF_CAP_CHARS * 1.5) + 10)
    _run("conv-1", f"對方叫小明。\n{huge}", monkeypatch)
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"
    assert load_self_memory(CONF) == ""


def test_placeholder_reply_does_not_write_self_memory(monkeypatch, tmp_path):
    """模型回傳佔位文字（純括號行）不該落地成她自己的記憶。"""
    _run("conv-1", "對方叫小明。\n（目前還沒有任何關於自己的記憶）", monkeypatch)
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"
    assert load_self_memory(CONF) == ""
    assert not (tmp_path / "chat_history" / CONF / "self_memory.md").exists()


def test_self_memory_is_shared_across_conversations(monkeypatch):
    _run("conv-a", "對方叫小明。\n紅莉栖喜歡咖啡。", monkeypatch)
    _run(
        "conv-b",
        "對方叫小華。\n紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。",
        monkeypatch,
    )
    assert load_core_memory(CONF, "conv-a") == "對方叫小明。"
    assert load_core_memory(CONF, "conv-b") == "對方叫小華。"
    assert load_self_memory(CONF) == "紅莉栖喜歡咖啡。\n紅莉栖討厭夏天。"


def test_existing_conversation_entry_that_is_actually_self_gets_migrated(monkeypatch):
    """模型把現有對話記憶裡其實是她自己的條目原樣回傳時，程式分類會把它搬到
    self，對話記憶不再含它——不需要模型自己判斷該搬去哪裡。
    """
    save_core_memory(CONF, "conv-1", "紅莉栖：認為時間是相對的概念")
    _run("conv-1", "對方叫小明。\n紅莉栖：認為時間是相對的概念", monkeypatch)
    assert load_core_memory(CONF, "conv-1") == "對方叫小明。"
    assert load_self_memory(CONF) == "紅莉栖：認為時間是相對的概念"


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
        return "\n".join([conv, *self_lines])

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


def test_protected_names_fold_misspelling_before_classification(monkeypatch):
    """整理輸出裡的錯字先被 normalize 折回正式寫法，才逐行分類。

    表裡帶了「紅莉栖」自己這條（跟 characters/kurisu.yaml 實際的寫法一致）：
    s2twp 會把「栖」當一般詞彙轉成「棲」，先跑過 OpenCC 才做 protected_names
    折字，角色名不折回來的話，這行就不再以角色名開頭，會被誤判進對話記憶
    而不是她自己的——這正是 fold 必須在分類「之前」跑的原因。
    """
    _run(
        "conv-1",
        "紅莉栖：記得杜拉比和椎名。",
        monkeypatch,
        reply_language="Traditional Chinese (Taiwan)",
        protected_names={"橋田至": ["杜拉比"], "紅莉栖": ["紅莉棲"]},
    )
    assert load_self_memory(CONF) == "紅莉栖：記得橋田至和椎名。"


def test_protected_names_not_folded_for_non_taiwan_language(monkeypatch):
    """語言不是台灣繁中時 normalize 本來就直接回傳原文，錯字原樣保留。"""
    _run(
        "conv-1",
        "紅莉栖：記得杜拉比和椎名。",
        monkeypatch,
        reply_language="Japanese",
        protected_names={"橋田至": ["杜拉比"]},
    )
    assert load_self_memory(CONF) == "紅莉栖：記得杜拉比和椎名。"


def test_without_the_new_kwargs_behavior_is_unchanged(monkeypatch):
    """不傳 reply_language／protected_names 時行為與現在一致：不折字。"""
    _run("conv-1", "紅莉栖：記得杜拉比和椎名。", monkeypatch)
    assert load_self_memory(CONF) == "紅莉栖：記得杜拉比和椎名。"


def test_different_characters_do_not_wait_for_each_other(monkeypatch):
    in_flight = 0
    peak = 0

    async def fake_rewrite(base_url, model, prompt, api_key, extra_body):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return "對方x\n角色y"

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
