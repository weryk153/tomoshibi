"""專有名詞保護必須由角色資料驅動，不能寫死在共用程式碼裡。

小模型會把專有名詞改成同音字（實測反覆把角色名字寫成同音字），OpenCC 的
s2twp 也會把專有名詞當一般詞彙做台灣用語轉換。所以「把正確寫法釘回去」這個機制
是需要的——需要被移出去的是「哪些名字」這份資料，那屬於角色，不屬於引擎。
"""

from src.open_llm_vtuber.conversation_quality import (
    normalize_output_language_variant,
)

ZH_TW = "Traditional Chinese (Taiwan)"


def test_supplied_protected_name_variant_is_restored():
    """名單由呼叫端給，函式照著把變體換回正式寫法。

    這裡刻意用一個跟本專案毫無關係的名字，才能證明是資料在驅動，
    而不是剛好命中某個寫死的規則。
    """
    out = normalize_output_language_variant(
        "今天的觀測由「愛萊」負責。",
        ZH_TW,
        protected_names={"愛徠": ["愛萊"]},
    )

    assert "愛徠" in out
    assert "愛萊" not in out


def test_no_character_name_is_hardcoded():
    """沒給名單就不該動任何專有名詞。

    這條是這次重構的重點：引擎裡不可以內建任何特定作品的角色名字。
    """
    out = normalize_output_language_variant("我是詠莉。", ZH_TW)

    assert out == "我是詠莉。"


def test_words_outside_the_list_are_untouched():
    """只保護名單上的字，句子裡其他地方不受影響。"""
    out = normalize_output_language_variant(
        "那傢伙的眼神有點兇。",
        ZH_TW,
        protected_names={"鳳凰院凶真": ["鳳凰院兇真"]},
    )

    assert "有點兇" in out


class _SilentWebSocket:
    async def send_text(self, payload):
        pass


async def _noop_conversation(*args, **kwargs):
    return ""


def test_proactive_prompt_falls_back_when_topics_were_never_saved(monkeypatch):
    """新裝好的人還沒存過主動話題，prompts/utils/proactive_speak_prompt.txt 不存在。

    這時要用內建的人設指示，不能退成一句 "Please say something."。
    """
    import asyncio
    from types import SimpleNamespace

    from src.open_llm_vtuber import news_topics
    from src.open_llm_vtuber.conversations import conversation_handler

    captured = {}

    async def _capture(**kwargs):
        captured.update(kwargs)

    def _missing(name):
        raise FileNotFoundError(name)

    monkeypatch.setattr(conversation_handler.prompt_loader, "load_util", _missing)
    monkeypatch.setattr(conversation_handler, "process_single_conversation", _capture)

    context = SimpleNamespace(
        character_config=SimpleNamespace(
            conf_uid="character",
            reply_language="Traditional Chinese (Taiwan)",
            protected_names={},
        ),
        system_config=SimpleNamespace(
            player_language="",
            tool_prompts={"proactive_speak_prompt": "proactive_speak_prompt"},
        ),
        history_uid="history",
        agent_engine=SimpleNamespace(),
    )

    asyncio.run(
        conversation_handler.handle_conversation_trigger(
            msg_type="ai-speak-signal",
            data={"idle_time": 60, "images": None},
            client_uid="client",
            context=context,
            websocket=_SilentWebSocket(),
            client_contexts={"client": context},
            client_connections={"client": _SilentWebSocket()},
            chat_group_manager=SimpleNamespace(get_client_group=lambda _uid: None),
            received_data_buffers={},
            current_conversation_tasks={},
            broadcast_to_group=None,
        )
    )

    # 規矩取自內建的提示，不是退成一句 "Please say something."。
    assert captured["metadata"]["proactive_instruction"].startswith(
        news_topics.INSTRUCTION.strip()[:20]
    )
