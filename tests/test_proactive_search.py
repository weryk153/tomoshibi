"""主動發言的即時搜尋 pass。

模式與 extract_proactive_visual_facts 相同：先中立判斷、真的去查、把結果
當事實塊注入主動 prompt。全程 fail-soft——任何一步失敗都退回原本的主動
發言行為。全部結構測試，不打真網路也不打真 LLM。
"""

import asyncio
from types import SimpleNamespace

from src.open_llm_vtuber.conversations.conversation_handler import (
    extract_proactive_search_facts,
)
from src.open_llm_vtuber.proactive_context import (
    build_proactive_prompt,
    clear_proactive_context,
    note_search_performed,
    search_cooldown_active,
)


class _FakeQueryLLM:
    """查詢 pass 用的假 LLM：回傳固定查詢詞。"""

    def __init__(self, reply: str):
        self._reply = reply
        self.calls = 0

    async def chat_completion(self, messages, system=None, tools=None):
        self.calls += 1
        yield self._reply


class _FakeMCPClient:
    def __init__(self, result: str = "", raises: bool = False):
        self.result = result
        self.raises = raises
        self.calls: list = []

    async def call_tool(self, server_name, tool_name, tool_args):
        self.calls.append((server_name, tool_name, tool_args))
        if self.raises:
            raise RuntimeError("network down")
        return {"content_items": [{"type": "text", "text": self.result}]}


def _context(
    llm_reply="NONE",
    use_mcpp=True,
    servers=("time", "ddg-search"),
    mcp_client=None,
    tools=None,
):
    agent = SimpleNamespace(_llm=_FakeQueryLLM(llm_reply))
    tool_manager = SimpleNamespace(
        tools=tools
        if tools is not None
        else {
            "search": SimpleNamespace(related_server="ddg-search"),
            "get_current_time": SimpleNamespace(related_server="time"),
        }
    )
    return SimpleNamespace(
        agent_engine=agent,
        mcp_client=mcp_client if mcp_client is not None else _FakeMCPClient(),
        tool_manager=tool_manager,
        character_config=SimpleNamespace(
            conf_uid="aoi",
            agent_config=SimpleNamespace(
                agent_settings=SimpleNamespace(
                    basic_memory_agent=SimpleNamespace(
                        use_mcpp=use_mcpp,
                        mcp_enabled_servers=list(servers),
                    )
                )
            ),
        ),
    )


ANCHOR = "使用者：最近在玩空洞騎士的新 DLC\n角色：絲之歌嗎？聽說做了很多年。"


def _run(context, anchor=ANCHOR, uid="search-test"):
    clear_proactive_context("aoi", uid)
    return asyncio.run(
        extract_proactive_search_facts(
            context,
            conversation_anchor=anchor,
            proactive_uid=uid,
            output_language="Traditional Chinese (Taiwan)",
        )
    )


# ---- 確定性閘門：任一不過就完全不花 LLM 呼叫 ----


def test_gate_skips_when_mcpp_disabled():
    context = _context(llm_reply="絲之歌 發售日", use_mcpp=False)
    assert _run(context) is None
    assert context.agent_engine._llm.calls == 0
    assert context.mcp_client.calls == []


def test_gate_skips_when_search_server_not_enabled():
    context = _context(llm_reply="絲之歌 發售日", servers=("time",))
    assert _run(context) is None
    assert context.agent_engine._llm.calls == 0


def test_gate_skips_when_anchor_empty():
    context = _context(llm_reply="絲之歌 發售日")
    assert _run(context, anchor="") is None
    assert context.agent_engine._llm.calls == 0


def test_gate_skips_when_no_search_tool_discovered():
    context = _context(
        llm_reply="絲之歌 發售日",
        tools={"get_current_time": SimpleNamespace(related_server="time")},
    )
    assert _run(context) is None
    assert context.agent_engine._llm.calls == 0


# ---- 查詢 pass ----


def test_none_verdict_performs_no_search():
    context = _context(llm_reply="NONE")
    assert _run(context) is None
    assert context.agent_engine._llm.calls == 1
    assert context.mcp_client.calls == []


def test_query_triggers_search_and_returns_facts():
    client = _FakeMCPClient(result="絲之歌 2026 年發售，首週銷量破百萬。")
    context = _context(llm_reply="空洞騎士 絲之歌 發售", mcp_client=client)
    facts = _run(context)
    assert facts is not None
    assert "絲之歌" in facts
    server, tool, args = client.calls[0]
    assert server == "ddg-search"
    assert tool == "search"
    assert "絲之歌" in str(args)


def test_search_failure_returns_none():
    client = _FakeMCPClient(raises=True)
    context = _context(llm_reply="空洞騎士 絲之歌", mcp_client=client)
    assert _run(context) is None


def test_empty_search_result_returns_none():
    client = _FakeMCPClient(result="   ")
    context = _context(llm_reply="空洞騎士 絲之歌", mcp_client=client)
    assert _run(context) is None


def test_facts_are_truncated():
    client = _FakeMCPClient(result="很長的結果" * 2000)
    context = _context(llm_reply="空洞騎士 絲之歌", mcp_client=client)
    facts = _run(context)
    assert facts is not None and len(facts) <= 1200


# ---- 冷卻 ----


def test_cooldown_blocks_second_search_in_window():
    clear_proactive_context("aoi", "cool")
    assert search_cooldown_active("aoi", "cool") is False
    note_search_performed("aoi", "cool", "絲之歌 發售")
    assert search_cooldown_active("aoi", "cool") is True


def test_cooldown_query_is_remembered():
    clear_proactive_context("aoi", "cool2")
    note_search_performed("aoi", "cool2", "絲之歌 發售")
    # 同 session 走冷卻擋，不需要比對查詢詞也會被擋；這裡驗證清除後恢復
    clear_proactive_context("aoi", "cool2")
    assert search_cooldown_active("aoi", "cool2") is False


def test_cooldown_gate_skips_without_llm_call():
    context = _context(llm_reply="絲之歌 發售日")
    clear_proactive_context("aoi", "cool3")
    note_search_performed("aoi", "cool3", "任何查詢")
    result = asyncio.run(
        extract_proactive_search_facts(
            context,
            conversation_anchor=ANCHOR,
            proactive_uid="cool3",
            output_language="Traditional Chinese (Taiwan)",
        )
    )
    assert result is None
    assert context.agent_engine._llm.calls == 0


# ---- prompt 注入 ----


def test_search_facts_block_appears_in_proactive_prompt():
    clear_proactive_context("aoi", "prompt-test")
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="aoi",
        client_uid="prompt-test",
        conversation_anchor=ANCHOR,
        output_language="Traditional Chinese (Taiwan)",
        verified_search_facts="絲之歌 2026 年發售，首週銷量破百萬。",
    )
    assert "## 已查到的即時資訊" in prompt
    assert "絲之歌 2026 年發售" in prompt
    assert "不要逐條播報" in prompt
    assert "不確定" in prompt


def test_no_search_facts_no_block():
    clear_proactive_context("aoi", "prompt-test2")
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="aoi",
        client_uid="prompt-test2",
        conversation_anchor=ANCHOR,
        output_language="Traditional Chinese (Taiwan)",
    )
    assert "## 已查到的即時資訊" not in prompt


# ---------------------------------------------------------------------------
# 換話題的許可。實測案例：使用者說「拜託跟我說」，她拒絕了（「你腦袋大概壞了吧」），
# 接著兩則主動發言還卡在那個已經講死的話題上自問自答（「誰說我喜歡那種東西的？」）。
# 原因是 prompt 三處都把延續寫成強制：錨點「必須直接承接」、短沉默「不要另開新題」。
# 一個被拒絕、被結束的話題正是最不該延續的情況。
# ---------------------------------------------------------------------------


def _anchor_prompt(**kw):
    clear_proactive_context("aoi", "topic-shift")
    return build_proactive_prompt(
        "基本指令",
        conf_uid="aoi",
        client_uid="topic-shift",
        conversation_anchor="使用者：拜託跟我說\n角色：拜託我這種事，你腦袋大概壞了吧。",
        output_language="Traditional Chinese (Taiwan)",
        **kw,
    )


def test_continuing_the_anchor_is_no_longer_mandatory():
    prompt = _anchor_prompt()
    assert "必須直接承接" not in prompt


def test_switching_topic_is_explicitly_allowed():
    prompt = _anchor_prompt()
    assert "換一個話題" in prompt


def test_closed_topics_are_named_as_a_reason_to_switch():
    """講死的話題要點名，不能只給模糊的許可。"""
    prompt = _anchor_prompt()
    assert "拒絕" in prompt or "講完了" in prompt


def test_short_silence_still_prefers_continuing_but_does_not_forbid_switching():
    """短沉默偏好延續是合理的，但不該是禁令。"""
    prompt = _anchor_prompt(idle_seconds=20)
    assert "不要突然另開" not in prompt


def test_anchor_consistency_rules_survive():
    """換題是新增的選項，不能把既有的一致性要求一起沖掉。"""
    prompt = _anchor_prompt()
    assert "不是使用者意圖正確無誤的證據" in prompt
    assert "不要沿著誤解繼續演下去" in prompt


def test_topic_switch_must_not_be_announced():
    """實測她說了「那我們就換個話題吧」——真人不會先報告自己要換話題。"""
    prompt = _anchor_prompt()
    assert "不要說「那我們換個話題」" in prompt
    assert "第一句就是新內容" in prompt


# ---------------------------------------------------------------------------
# 「不要硬回一句對方沒說過的話」。實測案例（2026-08-17 02:12）：使用者最後一句是
# 02:04 的「當然，這就是一番賞」，角色 02:05 已經回過了。使用者接著什麼都沒說，
# 主動發言卻冒出「嗯……你這樣說我也沒辦法反對啦」——把一句早就回完的舊訊息又回
# 了一次，聽起來像對方剛剛開口。
#
# 前一輪已經把錨點區塊放寬成「延續或換題都可以」，但規則區還留著一條沒改到的
# 硬性指令：「優先接住使用者最後提到的具體人物、事情、問題或感受」。它排在錨點
# 區塊後面、位置更接近輸出，實際壓過了那個自由選擇。
# ---------------------------------------------------------------------------


def _answered_anchor_prompt(**kw):
    clear_proactive_context("aoi", "already-answered")
    return build_proactive_prompt(
        "基本指令",
        conf_uid="aoi",
        client_uid="already-answered",
        conversation_anchor=(
            "使用者：當然，這就是一番賞\n"
            "角色：好吧，既然你這麼有把握……那就算我剛才幫你選的號碼是"
            "「特別開運」的預兆好了。"
        ),
        output_language="Traditional Chinese (Taiwan)",
        **kw,
    )


def test_no_surviving_order_to_answer_the_last_user_line():
    assert "優先接住使用者最後提到的" not in _answered_anchor_prompt()


def test_prompt_states_that_the_user_did_not_speak_this_turn():
    assert "這一輪使用者沒有說話" in _answered_anchor_prompt()


def test_already_answered_user_line_must_not_be_answered_again():
    prompt = _answered_anchor_prompt()
    assert "已經回過了" in prompt
    # 點名要禁的回應式開頭，光給抽象規則模型接不住。
    assert "你這樣說" in prompt


def test_addressing_the_user_is_offered_as_a_third_option():
    """使用者的原話：主動發言可以是找新話題，或是跟我搭話。"""
    assert "直接跟使用者搭話" in _answered_anchor_prompt()


def test_unanswered_user_line_is_not_wrongly_marked_as_answered():
    """錨點最後一句還是使用者的話時，那句確實還沒回過——不能叫她別回。"""
    clear_proactive_context("aoi", "unanswered")
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="aoi",
        client_uid="unanswered",
        conversation_anchor="角色：你要不要看看那個模型？\n使用者：我在想",
    )
    assert "已經回過了" not in prompt
