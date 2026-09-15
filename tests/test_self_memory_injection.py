"""系統提示注入兩塊：她自己的在前、對方的在後；任一份為空不出那一塊；長期記憶
關閉時兩份都不注入。

拉起 ServiceContext 整套太貴，這裡跟 tests/test_memory_call_sites.py 一樣用原始碼
斷言呼叫點，再用一個最小的 prompt 組裝函式做行為測試。
"""

import inspect

from src.open_llm_vtuber import service_context
from src.open_llm_vtuber.conversations import single_conversation
from src.open_llm_vtuber.service_context import build_memory_blocks

SELF_HEADER = "## 你對自己的認知（所有對話共用，自然運用、不要生硬複述）"
CONV_HEADER = "## 你對對方的長期記憶（之前對話累積下來的，自然運用、不要生硬複述）"


def test_self_block_comes_before_conversation_block():
    out = build_memory_blocks(self_mem="她喜歡咖啡。", core_mem="對方叫小明。")
    assert out.index(SELF_HEADER) < out.index(CONV_HEADER)
    assert "她喜歡咖啡。" in out
    assert "對方叫小明。" in out


def test_empty_self_omits_its_block():
    out = build_memory_blocks(self_mem="", core_mem="對方叫小明。")
    assert SELF_HEADER not in out
    assert CONV_HEADER in out


def test_empty_core_omits_its_block():
    out = build_memory_blocks(self_mem="她喜歡咖啡。", core_mem="")
    assert SELF_HEADER in out
    assert CONV_HEADER not in out


def test_both_empty_is_empty_string():
    assert build_memory_blocks(self_mem="", core_mem="") == ""


def test_system_prompt_injection_loads_both_under_the_enabled_gate():
    src = inspect.getsource(service_context.ServiceContext.construct_system_prompt)
    assert "load_self_memory(target_character.conf_uid)" in src
    assert "load_core_memory(target_character.conf_uid, self.history_uid)" in src
    assert "build_memory_blocks(" in src
    # 兩個 load 都要在 long_term_memory_enabled 的 if 底下
    gate = src.index('getattr(target_character, "long_term_memory_enabled", True)')
    assert src.index("load_self_memory(") > gate
    assert src.index("load_core_memory(") > gate


def test_mid_turn_refresh_compares_both_files():
    """中途重讀要拿「兩份一起」跟上一次注入的比，不是只比對話那份。

    斷言的是實際比較用的那個 tuple 本身（fresh_mem = (fresh_self, fresh_core)），
    不是鬆散的「_core_mem_injected 這個詞有出現」——後者在只重讀 core、self 沒
    納入比較時一樣會通過。
    """
    src = inspect.getsource(single_conversation.process_single_conversation)
    assert "load_self_memory(context.character_config.conf_uid)" in src
    assert "fresh_mem = (fresh_self, fresh_core)" in src
    assert "context._core_mem_injected = fresh_mem" in src
