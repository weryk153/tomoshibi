import asyncio
from types import SimpleNamespace

import pytest

from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from src.open_llm_vtuber.conversation_quality import (
    build_turn_guidance,
    normalize_output_language_variant,
)
from src.open_llm_vtuber.proactive_context import (
    MAX_RECENT_PROACTIVE,
    clear_proactive_context,
    get_recent_proactive,
    proactive_context_uid,
    record_proactive_response,
)


class _FakeVisionFactLLM:
    def __init__(self):
        self.messages = None
        self.system = None

    async def chat_completion(self, messages, system=None, tools=None):
        self.messages = messages
        self.system = system
        yield "- 編輯器顯示 service_context.py\n"
        yield "- 底部是終端機"


def _batch(text: str, *, skip_memory: bool) -> BatchInput:
    return BatchInput(
        texts=[TextData(source=TextSource.INPUT, content=text)],
        metadata={"skip_memory": skip_memory},
    )


def test_history_identity_keeps_proactive_context_across_socket_reconnects():
    history_uid = "2026-07-30_history"
    first_socket = proactive_context_uid(history_uid, "socket-a")
    second_socket = proactive_context_uid(history_uid, "socket-b")

    assert first_socket == second_socket == history_uid

    clear_proactive_context("character", first_socket)
    record_proactive_response("character", first_socket, "這是上一條主動發言。")
    assert get_recent_proactive("character", second_socket) == ["這是上一條主動發言。"]


def test_chinese_yes_no_question_gets_one_matching_direct_answer_pair():
    instruction = build_turn_guidance("你剛才有沒有覺得我把你測得很煩？")

    assert "「有」或「沒有」其中一個" in instruction
    assert "「有沒有」不是答案" in instruction
    assert "禁止複誦原問題或用反問迴避" in instruction
    assert "會／不會" not in instruction


@pytest.mark.parametrize("text", ["看你", "隨你。", "都可以", "你決定！"])
def test_delegated_choice_short_reply_gets_contextual_resolution_hint(text):
    instruction = build_turn_guidance(text)

    assert "意思是『你決定』" in instruction
    assert "直接替當下話題選一個具體選項" in instruction
    assert "不要另加第二個活動" in instruction
    assert "不得捏造兩人以前一起做過什麼的共同回憶" in instruction
    assert "禁止把『看你』解讀成凝視角色" in instruction
    assert "看我會失望" in instruction


def test_literal_looking_phrase_does_not_trigger_delegated_choice_hint():
    assert build_turn_guidance("我正在看你") == ""


@pytest.mark.parametrize(
    "text",
    ["我已經盡力了。", "我真的很努力了", "我撐不下去了", "我好累。"],
)
def test_vulnerable_effort_statement_gets_emotional_acknowledgement_hint(text):
    instruction = build_turn_guidance(text)

    assert "不是在請你定義或辯論『盡力』" in instruction
    assert "第一句先用自然的人話承認對方的付出或辛苦" in instruction
    assert "禁止反問『盡力是什麼意思』" in instruction
    assert "全程用『我』自稱" in instruction
    assert "不用角色自己的名字作第三人稱自稱" in instruction
    assert "整體一到三句" in instruction


def test_neutral_effort_question_does_not_force_vulnerability_handling():
    assert build_turn_guidance("怎樣才算盡力？") == ""


@pytest.mark.parametrize(
    "text",
    [
        "你也是走得很前面哦。",
        "你已經做得很全面了。",
        "你真的很厲害耶！",
        "妳做得很好。",
    ],
)
def test_friendly_praise_gets_charitable_asr_tolerant_hint(text):
    instruction = build_turn_guidance(text)

    assert "明顯意圖是友善稱讚" in instruction
    assert "先接住善意" in instruction
    assert "只處理『你做得很全面，也走在很前面』這層意思" in instruction
    assert "不引用或評論使用者原句的任何字詞" in instruction
    assert "第一句只能是道謝或接受稱讚" in instruction
    assert "禁止用『不過』轉回檢討使用者的措辭" in instruction
    assert "禁止逐字追問定義" in instruction
    assert "自以為是或可笑" in instruction
    assert "不要評論這種說法很奇怪、彆扭或用詞不準" in instruction


def test_genuine_definition_question_does_not_force_praise_handling():
    assert build_turn_guidance("走得很前面是什麼意思？") == ""


def test_taiwan_language_setting_normalizes_script_and_regional_terms():
    assert (
        normalize_output_language_variant(
            "咱們看看视频和软件里的信息，纔知道這事兒。",
            "Traditional Chinese (Taiwan)",
        )
        == "我們看看影片和軟體裡的資訊，才知道這事情。"
    )
    assert (
        normalize_output_language_variant(
            "咱們看看视频",
            "Simplified Chinese",
        )
        == "咱們看看视频"
    )
    # 專有名詞的保護由呼叫端給名單（角色資料），引擎本身不認得任何角色名字。
    assert (
        normalize_output_language_variant(
            "我是月島泳梨。人類よ。",
            "Traditional Chinese (Taiwan)",
            protected_names={"詠梨": ["詠莉", "泳梨", "詠利"]},
        )
        == "我是月島詠梨。人類。"
    )
    assert (
        normalize_output_language_variant(
            "這是頁面頁面 頁面，PAGE PAGE PAGE PAGE。",
            "Traditional Chinese (Taiwan)",
        )
        == "這是頁面，PAGE。"
    )
    assert (
        normalize_output_language_variant(
            "「這麼被誇獎……雖然有點意外，不過還是謝謝。」",
            "Traditional Chinese (Taiwan)",
        )
        == "這麼被誇獎……雖然有點意外，不過還是謝謝。"
    )
    assert (
        normalize_output_language_variant(
            "我說的是「謝謝」，不是別的。",
            "Traditional Chinese (Taiwan)",
        )
        == "我說的是「謝謝」，不是別的。"
    )


def test_recent_proactive_window_is_bounded_per_session():
    clear_proactive_context("character", "client")
    for index in range(MAX_RECENT_PROACTIVE + 2):
        record_proactive_response("character", "client", f"第 {index} 句")

    recent = get_recent_proactive("character", "client")

    assert len(recent) == MAX_RECENT_PROACTIVE
    assert recent[0] == "第 2 句"
    assert recent[-1] == f"第 {MAX_RECENT_PROACTIVE + 1} 句"


# ---------------------------------------------------------------------------
# 「我說一句結果他一直說」：一句真人發言之後，主動發言連續獨白十幾則。
# 三個獨立缺陷合起來造成的，以下分別鎖住。
# ---------------------------------------------------------------------------


def _proactive_trigger_context(conf_uid: str, history_uid: str):
    return SimpleNamespace(
        character_config=SimpleNamespace(
            conf_uid=conf_uid,
            reply_language="Traditional Chinese (Taiwan)",
        ),
        system_config=SimpleNamespace(
            player_language="",
            tool_prompts={},
        ),
        history_uid=history_uid,
        agent_engine=SimpleNamespace(),
    )


class _RecordingWebSocket:
    def __init__(self):
        self.sent = []

    async def send_text(self, payload):
        self.sent.append(payload)


async def _run_trigger(context, websocket, idle_time, tasks):
    from src.open_llm_vtuber.conversations.conversation_handler import (
        handle_conversation_trigger,
    )

    await handle_conversation_trigger(
        msg_type="ai-speak-signal",
        data={"idle_time": idle_time, "images": None},
        client_uid="client",
        context=context,
        websocket=websocket,
        client_contexts={"client": context},
        client_connections={"client": websocket},
        chat_group_manager=SimpleNamespace(get_client_group=lambda _uid: None),
        received_data_buffers={},
        current_conversation_tasks=tasks,
        broadcast_to_group=None,
    )


def test_hand_raise_button_still_works():
    """舉手按鈕是使用者主動要求（idle_time=-1），一直都能用。"""
    conf, history = "character", "budget-manual"
    clear_proactive_context(conf, history)
    for index in range(10):
        record_proactive_response(conf, history, f"主動發言第 {index} 則。")

    context = _proactive_trigger_context(conf, history)
    websocket = _RecordingWebSocket()
    tasks = {}

    asyncio.run(_run_trigger(context, websocket, idle_time=-1, tasks=tasks))

    assert "client" in tasks
    tasks["client"].cancel()


def _fetch_history_handler(cleared):
    import src.open_llm_vtuber.websocket_handler as ws_module
    from src.open_llm_vtuber.websocket_handler import WebSocketHandler

    context = _proactive_trigger_context("character", "old-history")
    context.agent_engine = None
    # A real (uninitialised) instance rather than a namespace: switching history
    # goes through sibling methods on the handler, which a namespace lacks.
    handler = WebSocketHandler.__new__(WebSocketHandler)
    handler.client_contexts = {"client": context}
    return ws_module, handler, context


def test_switching_history_clears_the_context_under_its_real_key(monkeypatch):
    """記錄／讀取都用 proactive_context_uid(history_uid or client_uid)，
    清除卻只傳 client_uid——所以切換歷史時根本沒清到。"""
    import src.open_llm_vtuber.websocket_handler as ws_module
    from src.open_llm_vtuber.websocket_handler import WebSocketHandler

    cleared = []
    monkeypatch.setattr(
        ws_module,
        "clear_proactive_context",
        lambda conf_uid, client_uid: cleared.append((conf_uid, client_uid)),
    )
    monkeypatch.setattr(ws_module, "get_history", lambda *_args, **_kwargs: [])
    # Keep the resume pointer out of it — this test is about proactive context,
    # and it must not write state into the real chat_history/ directory.
    monkeypatch.setattr(
        ws_module, "set_active_history_uid", lambda *_args, **_kwargs: None
    )

    _module, handler, _context = _fetch_history_handler(cleared)
    websocket = _RecordingWebSocket()

    asyncio.run(
        WebSocketHandler._handle_fetch_history(
            handler, websocket, "client", {"history_uid": "new-history"}
        )
    )

    assert cleared == [("character", "old-history")]


def test_proactive_synthetic_prompt_gets_no_user_intent_rule():
    """主動回合的文字是合成指令，不是使用者說的話。

    是非題那條規則用子字串比對，合成 prompt 只要出現「有沒有」就會誤觸，
    在一個沒有使用者提問的回合裡硬塞一條回答結構要求。
    """
    synthetic = "請自然地接續剛才的話題，並確認背後有沒有什麼值得一提的細節。"

    assert build_turn_guidance(synthetic, is_proactive=True) == ""
    assert build_turn_guidance(synthetic, is_proactive=False) != ""


def test_only_the_first_matching_user_intent_rule_is_applied():
    """四條規則維持首個命中即返回，不得疊加。"""
    both = "我已經盡力了，你有沒有在聽？"

    guidance = build_turn_guidance(both)

    assert "第一句先用自然的人話承認對方的付出或辛苦" in guidance
    assert "「有沒有」不是答案" not in guidance


def test_turn_guidance_is_empty_for_an_ordinary_sentence():
    assert build_turn_guidance("今天實驗室很安靜。") == ""


def test_mainland_only_idioms_written_in_traditional_are_localised():
    """s2twp 轉的是字，不是慣用語。

    實測（logs/debug_2026-08-17.log:4486）畫面上出現「腦袋完全在開小差吧？」——
    整句都是繁體字，s2twp 因此原樣放行，而既有的 taiwan_terms 只蓋科技名詞
    （用戶／程序／軟件／視頻…）和幾個口語詞，陸語慣用語一條都沒有。
    """
    assert (
        normalize_output_language_variant(
            "你、你這傢伙，腦袋完全在開小差吧？",
            "Traditional Chinese (Taiwan)",
        )
        == "你、你這傢伙，腦袋完全在恍神吧？"
    )
    assert (
        normalize_output_language_variant(
            "我剛才走神了，而且對這件事沒轍。",
            "Traditional Chinese (Taiwan)",
        )
        == "我剛才恍神了，而且對這件事沒辦法。"
    )
    assert (
        normalize_output_language_variant(
            "別想忽悠我，那個攝像頭根本沒開。",
            "Traditional Chinese (Taiwan)",
        )
        == "別想唬弄我，那個攝影機根本沒開。"
    )


def test_physics_and_ambiguous_words_are_left_alone():
    """角色是腦科學研究者：「質量」是 mass，不是品質。

    同理「水平」在台灣也常指水平方向、「估計」「搞定」兩地都在用——這些改下去
    會把正確的句子改壞，代價比留著陸語味道大得多。
    """
    text = "這個粒子的質量與水平方向的分量，我估計一下就能搞定。"
    assert (
        normalize_output_language_variant(text, "Traditional Chinese (Taiwan)") == text
    )
