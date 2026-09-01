"""專有名詞保護必須由角色資料驅動，不能寫死在共用程式碼裡。

小模型會把專有名詞改成同音字（實測反覆把「紅莉栖」寫成「紅麗棲」），OpenCC 的
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
    out = normalize_output_language_variant("我是紅麗棲。", ZH_TW)

    assert out == "我是紅麗棲。"


def test_words_outside_the_list_are_untouched():
    """只保護名單上的字，句子裡其他地方不受影響。"""
    out = normalize_output_language_variant(
        "那傢伙的眼神有點兇。",
        ZH_TW,
        protected_names={"鳳凰院凶真": ["鳳凰院兇真"]},
    )

    assert "有點兇" in out


def test_proactive_anchor_uses_the_characters_protected_names():
    """主動說話的錨點會經過正規化，名單要一路傳到那裡。

    錨點取自對話記憶，模型先前的錯字會原樣回流到 prompt 裡，等於把錯誤寫法
    再示範一次給它看。所以這條路徑也要吃得到角色的名單。
    """
    from src.open_llm_vtuber.proactive_context import build_proactive_prompt

    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="client",
        output_language="Traditional Chinese (Taiwan)",
        conversation_anchor="角色：這件事交給愛萊處理。",
        protected_names={"愛徠": ["愛萊"]},
    )

    assert "愛徠" in prompt
    assert "愛萊" not in prompt


def test_conversation_handler_forwards_the_characters_protected_names(monkeypatch):
    """名單住在角色設定裡，handler 負責把它交給 prompt 建構。

    這一段是整條線唯一沒被其他測試覆蓋的接點：前面驗證了函式會用名單，
    這裡驗證名單真的從角色設定流得過來。
    """
    import asyncio
    from types import SimpleNamespace

    from src.open_llm_vtuber.conversations import conversation_handler

    captured = {}

    def _capture(*args, **kwargs):
        captured.update(kwargs)
        return "prompt"

    monkeypatch.setattr(conversation_handler, "build_proactive_prompt", _capture)
    monkeypatch.setattr(
        conversation_handler, "process_single_conversation", _noop_conversation
    )

    context = SimpleNamespace(
        character_config=SimpleNamespace(
            conf_uid="character",
            reply_language="Traditional Chinese (Taiwan)",
            protected_names={"愛徠": ["愛萊"]},
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

    assert captured.get("protected_names") == {"愛徠": ["愛萊"]}


class _SilentWebSocket:
    async def send_text(self, payload):
        pass


async def _noop_conversation(*args, **kwargs):
    return ""
