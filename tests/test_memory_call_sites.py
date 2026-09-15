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


def test_consolidation_passes_reply_language_and_protected_names():
    """整理呼叫要帶上這個角色的語言與專有名詞表，否則整理出來的記憶不會套
    normalize_output_language_variant，錯字（如「杜拉比」）會原樣寫進檔案。
    """
    src = inspect.getsource(single_conversation.process_single_conversation)
    assert "consolidate_core_memory(" in src
    assert "reply_language=_effective_output_language(context)" in src
    assert "protected_names=" in src


def test_every_normalize_call_passes_the_protected_names_table():
    """process_single_conversation 與 _speak 裡，每一個
    normalize_output_language_variant( 呼叫都要帶 _protected(context)，
    不然一般回覆的顯示/TTS 文字不會套這個角色的專有名詞表。
    """
    for func in (
        single_conversation._speak,
        single_conversation.process_single_conversation,
    ):
        src = inspect.getsource(func)
        total = src.count("normalize_output_language_variant(")
        protected = src.count("_protected(context)")
        assert total > 0, (
            f"{func.__name__} 裡沒有 normalize_output_language_variant( 呼叫"
        )
        assert total == protected, (
            f"{func.__name__} 裡有 {total} 個 normalize_output_language_variant( 呼叫，"
            f"但只有 {protected} 個帶了 _protected(context)"
        )
