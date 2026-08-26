"""三個行程內呼叫點都必須把 history_uid 帶進記憶層。

漏掉任何一個，那條路徑就會用舊的角色層路徑或直接 TypeError。這裡用原始碼檢查
而不是行為測試，是因為要跑到那三行需要拉起 agent、TTS、WebSocket 一整套；
成本遠高於它能抓到的東西。真正的行為驗證在 Task 5 的手動步驟。

三個測試都斷言呼叫點的「確切文字」（含參數順序、換行位置），而不是鬆散的
「history_uid 這個詞有沒有出現在函式原始碼裡任何地方」——後者就算改動的是
完全不相關的那一行也會通過，抓不到呼叫點本身漏掉 history_uid 的情況。
"""

import inspect

from src.open_llm_vtuber import service_context
from src.open_llm_vtuber.conversations import single_conversation


def test_system_prompt_injection_uses_the_conversation():
    src = inspect.getsource(service_context.ServiceContext.construct_system_prompt)
    assert "load_core_memory(target_character.conf_uid, self.history_uid)" in src


def test_mid_turn_refresh_uses_the_conversation():
    src = inspect.getsource(single_conversation.process_single_conversation)
    assert (
        "load_core_memory(\n"
        "                    context.character_config.conf_uid, context.history_uid\n"
        "                )"
    ) in src, (
        "phase 1.5 的中途重讀沒有把 context.history_uid 緊跟在 conf_uid 之後傳進去"
    )


def test_consolidation_passes_the_conversation_first():
    src = inspect.getsource(single_conversation.process_single_conversation)
    assert (
        "consolidate_core_memory(\n"
        "                            _conf_uid,\n"
        "                            context.history_uid,\n"
        "                            input_text,\n"
        "                            full_response,\n"
    ) in src, "背景整理呼叫的 history_uid 沒有緊接在 conf_uid 之後"
