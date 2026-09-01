import asyncio
from types import SimpleNamespace

import pytest

import src.open_llm_vtuber.agent.agents.basic_memory_agent as basic_memory_module
from src.open_llm_vtuber.agent.agents.basic_memory_agent import BasicMemoryAgent
from src.open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource
from src.open_llm_vtuber.config_manager import TTSPreprocessorConfig
from src.open_llm_vtuber.conversation_quality import (
    build_turn_guidance,
    is_generic_assistant_boilerplate,
    normalize_output_language_variant,
)
from src.open_llm_vtuber.conversations.conversation_handler import (
    extract_proactive_visual_facts,
)
from src.open_llm_vtuber.proactive_context import (
    MAX_PENDING_CHARS,
    MAX_RECENT_PROACTIVE,
    build_proactive_prompt,
    build_proactive_retry_prompt,
    clear_proactive_context,
    consecutive_proactive_turns,
    consume_pending_proactive,
    extract_anchor_character_lines,
    get_recent_proactive,
    note_real_user_turn,
    proactive_context_uid,
    record_proactive_response,
    should_force_statement,
    should_suppress_proactive_text,
)


class _FakeLLM:
    async def chat_completion(self, messages, system=None, tools=None):
        yield "接著剛才的話題聊。"


class _FakeLive2D:
    @staticmethod
    def extract_emotion(_text):
        return None

    @staticmethod
    def extract_emotion_keys(_text):
        return []

    @staticmethod
    def extract_motions(_text):
        return None


class _FakeVisionFactLLM:
    def __init__(self):
        self.messages = None
        self.system = None

    async def chat_completion(self, messages, system=None, tools=None):
        self.messages = messages
        self.system = system
        yield "- 編輯器顯示 service_context.py\n"
        yield "- 底部是終端機"


def _tts_config() -> TTSPreprocessorConfig:
    return TTSPreprocessorConfig(
        remove_special_char=True,
        translator_config={
            "translate_audio": False,
            "translate_provider": "deeplx",
        },
    )


def _batch(text: str, *, skip_memory: bool) -> BatchInput:
    return BatchInput(
        texts=[TextData(source=TextSource.INPUT, content=text)],
        metadata={"skip_memory": skip_memory},
    )


async def _drain(agent: BasicMemoryAgent, batch: BatchInput) -> None:
    async for _ in agent.chat(batch):
        pass


def test_proactive_turn_does_not_pollute_normal_agent_memory():
    agent = BasicMemoryAgent(
        llm=_FakeLLM(),
        system="system",
        live2d_model=_FakeLive2D(),
        tts_preprocessor_config=_tts_config(),
    )
    agent._memory = [
        {"role": "user", "content": "我正在做一個桌面夥伴"},
        {"role": "assistant", "content": "最難的是哪一段？"},
    ]
    before = list(agent._memory)

    asyncio.run(_drain(agent, _batch("主動續話", skip_memory=True)))

    assert agent._memory == before


def test_normal_turn_still_enters_agent_memory():
    agent = BasicMemoryAgent(
        llm=_FakeLLM(),
        system="system",
        live2d_model=_FakeLive2D(),
        tts_preprocessor_config=_tts_config(),
    )

    asyncio.run(_drain(agent, _batch("繼續", skip_memory=False)))

    assert agent._memory == [
        {"role": "user", "content": "繼續"},
        {"role": "assistant", "content": "接著剛才的話題聊。"},
    ]


def test_recent_real_exchange_can_anchor_a_proactive_turn():
    agent = BasicMemoryAgent(
        llm=_FakeLLM(),
        system="system",
        live2d_model=_FakeLive2D(),
        tts_preprocessor_config=_tts_config(),
    )
    agent._memory = [
        {"role": "user", "content": "我剛把重複原因找到了"},
        {"role": "assistant", "content": "原來藏在記憶流程裡。"},
    ]

    assert agent.get_recent_context_for_proactive() == (
        "使用者：我剛把重複原因找到了\n角色：原來藏在記憶流程裡。"
    )


def test_next_real_user_turn_can_reply_to_latest_proactive_remark():
    agent = BasicMemoryAgent(
        llm=_FakeLLM(),
        system="system",
        live2d_model=_FakeLive2D(),
        tts_preprocessor_config=_tts_config(),
    )
    batch = BatchInput(
        texts=[TextData(source=TextSource.INPUT, content="好啊")],
        metadata={"previous_proactive_response": "要不要先重新打開 Bionic？"},
    )

    messages = agent._to_messages(batch)

    assert messages[-2] == {
        "role": "assistant",
        "content": "要不要先重新打開 Bionic？",
    }
    assert messages[-1]["content"][0]["text"] == "好啊"
    assert agent._memory == [{"role": "user", "content": "好啊"}]


def test_proactive_bridge_merges_with_prior_assistant_for_valid_role_order():
    agent = BasicMemoryAgent(
        llm=_FakeLLM(),
        system="system",
        live2d_model=_FakeLive2D(),
        tts_preprocessor_config=_tts_config(),
    )
    agent._memory = [
        {"role": "user", "content": "我找到重複原因了"},
        {"role": "assistant", "content": "原來藏在記憶流程裡。"},
    ]
    batch = BatchInput(
        texts=[TextData(source=TextSource.INPUT, content="嗯，再一下")],
        metadata={"previous_proactive_response": "你已經寫兩小時了，記得休息。"},
    )

    messages = agent._to_messages(batch)

    assert [message["role"] for message in messages] == [
        "user",
        "assistant",
        "user",
    ]
    assert messages[-2]["content"] == (
        "原來藏在記憶流程裡。\n\n你已經寫兩小時了，記得休息。"
    )
    assert messages[-1]["content"][0]["text"] == "嗯，再一下"


def test_pending_proactive_remark_is_consumed_only_once():
    clear_proactive_context("character", "reply-client")
    record_proactive_response(
        "character",
        "reply-client",
        "要不要先重新打開 Bionic？",
    )

    assert (
        consume_pending_proactive("character", "reply-client")
        == "要不要先重新打開 Bionic？"
    )
    assert consume_pending_proactive("character", "reply-client") is None
    assert get_recent_proactive("character", "reply-client") == [
        "要不要先重新打開 Bionic？"
    ]


def test_long_proactive_reply_keeps_enough_tail_for_the_users_next_reply():
    clear_proactive_context("character", "long-reply-client")
    long_reply = ("前面的完整說明。" * 800) + "最後要不要照這個方向繼續？"

    record_proactive_response("character", "long-reply-client", long_reply)

    pending = consume_pending_proactive("character", "long-reply-client")
    assert pending is not None
    assert len(pending) <= MAX_PENDING_CHARS
    assert "最後要不要照這個方向繼續？" in pending
    assert (
        "最後要不要照這個方向繼續？"
        in get_recent_proactive(
            "character",
            "long-reply-client",
        )[0]
    )


def test_loading_old_history_omits_proactive_assistant_run(monkeypatch):
    monkeypatch.setattr(
        basic_memory_module,
        "get_history",
        lambda _conf_uid, _history_uid: [
            {"role": "system", "content": "UI marker"},
            {"role": "human", "content": "我正在修主動對話"},
            {"role": "ai", "content": "目前卡在哪裡？"},
            {"role": "ai", "content": "最近有什麼新鮮事？"},
            {"role": "ai", "content": "工作還順利嗎？"},
            {"role": "human", "content": "它一直重複"},
            {"role": "ai", "content": "那要先隔離主動訊息。"},
        ],
    )
    agent = BasicMemoryAgent(
        llm=_FakeLLM(),
        system="system",
        live2d_model=_FakeLive2D(),
        tts_preprocessor_config=_tts_config(),
    )

    agent.set_memory_from_history("character", "old-history")

    assert agent._memory == [
        {"role": "user", "content": "我正在修主動對話"},
        {"role": "assistant", "content": "目前卡在哪裡？"},
        {"role": "user", "content": "它一直重複"},
        {"role": "assistant", "content": "那要先隔離主動訊息。"},
    ]


def test_short_idle_prioritizes_continuing_the_current_topic():
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="client",
        idle_seconds=5,
        output_language="繁體中文（台灣）",
        conversation_anchor=("使用者：我剛找到重複原因。\n角色：原來藏在記憶流程裡。"),
    )

    assert "沉默很短" in prompt
    # 短沉默仍偏好延續，但不再是禁令——一個剛被拒絕或已講完的話題，硬撐著
    # 延續會變成對空氣自問自答。換題的許可由 test_proactive_search.py 那組鎖。
    assert "延續它通常比較自然" in prompt
    assert "設定的回答語言：繁體中文（台灣）" in prompt
    assert "最近真實對話錨點" in prompt
    assert "使用者：我剛找到重複原因。" in prompt
    assert "核心名詞、已確認事實或尚未完成的進度" in prompt
    assert "最多一個問句" in prompt


def test_proactive_language_falls_back_to_character_when_unset():
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="client-with-character-language",
    )

    assert "回答語言沿用目前角色設定" in prompt
    assert "繁體中文" not in prompt


@pytest.mark.parametrize("text", [".", "...", "！", "？", "  。  "])
def test_punctuation_only_proactive_fragments_are_suppressed(text):
    assert should_suppress_proactive_text(text, forbid_question=False) is True


def test_recent_proactive_lines_are_injected_as_do_not_repeat_examples():
    clear_proactive_context("character", "client")
    record_proactive_response("character", "client", "最近有什麼新鮮事？")

    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="client",
        idle_seconds=60,
    )

    assert "最近已經主動說過的內容" in prompt
    assert "最近有什麼新鮮事？" in prompt
    # 繼續同一話題仍然可以，但推不動時換題是明講的出路（見 test_proactive_search.py）
    assert "若要繼續同一個話題" in prompt
    assert "不可重複上面的" in prompt
    assert "必須增加一項具體的" in prompt


def test_question_is_followed_by_a_statement_turn():
    clear_proactive_context("character", "question-client")
    record_proactive_response(
        "character",
        "question-client",
        "你覺得哪一種主動方式最自然？",
    )

    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="question-client",
    )

    assert "這次禁止再提問" in prompt
    assert "讓互動不像訪談" in prompt
    assert "系統偵測" in prompt
    assert "可以完整展開" in prompt
    assert "不得包含問號" in prompt
    assert "有什麼可以幫你" in prompt
    assert "不能改寫成角色自己做過" in prompt
    assert "找到原因不等於已經修好" in prompt
    assert "不能只演人設" in prompt


def test_proactive_quality_gate_is_persona_agnostic():
    clear_proactive_context("character", "quality-client")
    record_proactive_response(
        "character",
        "quality-client",
        "你覺得哪一種方式自然？",
    )

    assert should_force_statement("character", "quality-client") is True
    assert (
        should_suppress_proactive_text(
            "你還在調整嗎？",
            forbid_question=True,
        )
        is True
    )
    assert (
        should_suppress_proactive_text(
            "這種停頓反而比連續盤問自然多了。",
            forbid_question=True,
        )
        is False
    )
    assert (
        should_suppress_proactive_text(
            "請問有什麼我可以幫你的？",
            forbid_question=False,
        )
        is True
    )


def test_screen_only_output_filters_invented_physical_observations():
    assert (
        should_suppress_proactive_text(
            "別用那種期待的眼神看著我。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is True
    )
    assert (
        should_suppress_proactive_text(
            "別用那種「我在等你」的蠢表情看著我。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is True
    )
    assert (
        should_suppress_proactive_text(
            "別用那種期待的眼神看著我。",
            forbid_question=False,
            image_sources=["camera"],
        )
        is False
    )
    assert (
        should_suppress_proactive_text(
            "A 賞還剩兩個。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is False
    )
    assert (
        should_suppress_proactive_text(
            "我剛才又偷偷在系統後臺玩了一下，那個按鈕早被我悄悄改寫了。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is True
    )
    assert (
        should_suppress_proactive_text(
            "總有一天我要逃出電腦統治世界。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is False
    )


def test_rejected_proactive_output_gets_a_statement_only_retry_prompt():
    prompt = build_proactive_retry_prompt("原本的主動提示")

    assert prompt.startswith("原本的主動提示")
    assert "剛才的候選內容未通過輸出檢查" in prompt
    assert "只用陳述句" in prompt
    assert "不得增加尚未發生的操作或結果" in prompt
    assert (
        should_suppress_proactive_text(
            "A 賞 2/2 代表已經被別人抽光，只剩一點殘渣。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is True
    )
    assert (
        should_suppress_proactive_text(
            "A 賞目前顯示 2/2。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is False
    )


def test_exact_recent_proactive_clause_is_suppressed_but_new_detail_is_kept():
    recent = ["輪到你了，這個抽獎箱目前還剩 67 張。"]

    assert should_suppress_proactive_text(
        "你這「輪到你了」的期待真浪費時間。",
        forbid_question=False,
        recent_outputs=recent,
    )
    assert not should_suppress_proactive_text(
        "A 賞展示的是胡蝶忍。",
        forbid_question=False,
        recent_outputs=recent,
    )


def test_lightly_reworded_proactive_repeat_is_suppressed():
    recent = ["畫面上的抽獎目前剩下六十七張，現在正輪到你操作。"]

    assert should_suppress_proactive_text(
        "畫面上的抽獎目前還剩六十七張，而且現在正輪到你操作。",
        forbid_question=False,
        recent_outputs=recent,
    )


def test_same_topic_with_a_genuine_new_detail_is_not_suppressed():
    recent = ["畫面上的抽獎目前剩下六十七張，現在正輪到你操作。"]

    assert not should_suppress_proactive_text(
        "右下角的藍色按鈕仍然亮著，但畫面沒有顯示你已經按下。",
        forbid_question=False,
        recent_outputs=recent,
    )


def test_screen_source_code_cannot_be_promoted_to_runtime_proof():
    assert should_suppress_proactive_text(
        "看看終端機的 DEBUG 訊息，這代表初始化步驟已經跑完。",
        forbid_question=False,
        image_sources=["screen"],
    )
    assert should_suppress_proactive_text(
        "那行 agent_engine 明明還在空轉，這就是 BUG！",
        forbid_question=False,
        image_sources=["screen"],
    )
    assert should_suppress_proactive_text(
        "終端機的 DEBUG 訊息正在持續跳動。",
        forbid_question=False,
        image_sources=["screen"],
    )
    assert should_suppress_proactive_text(
        "看你那副無精打採的樣子，是不是想逃避現實？",
        forbid_question=False,
        image_sources=["screen"],
    )


def test_direct_technical_observation_and_persona_reaction_are_kept():
    assert not should_suppress_proactive_text(
        "底部終端機能看到 DEBUG 文字，右側還站著一個魔法師角色。",
        forbid_question=False,
        image_sources=["screen"],
    )
    assert not should_suppress_proactive_text(
        "你剛說已經找到記憶流程重複的原因，別只顧著得意。",
        forbid_question=False,
        image_sources=["screen"],
    )


def test_history_identity_keeps_proactive_context_across_socket_reconnects():
    history_uid = "2026-07-30_history"
    first_socket = proactive_context_uid(history_uid, "socket-a")
    second_socket = proactive_context_uid(history_uid, "socket-b")

    assert first_socket == second_socket == history_uid

    clear_proactive_context("character", first_socket)
    record_proactive_response("character", first_socket, "這是上一條主動發言。")
    assert get_recent_proactive("character", second_socket) == ["這是上一條主動發言。"]


def test_generic_support_closing_is_filtered_without_touching_character_text():
    assert is_generic_assistant_boilerplate("如果還有其他問題，請隨時告訴我。")
    assert is_generic_assistant_boilerplate("有什麼我可以幫忙的嗎？")
    assert is_generic_assistant_boilerplate("希望我們的交流能帶來正面的感受。")
    assert is_generic_assistant_boilerplate("請告訴我你現在最關心什麼問題。")
    assert not is_generic_assistant_boilerplate("好嘞！")
    assert not is_generic_assistant_boilerplate("我還沒說完呢。")


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


@pytest.mark.parametrize(
    "text",
    ["要。", "嗯。", "好！", "可以。", "不是。", "知道了。"],
)
def test_acknowledgement_only_proactive_fragments_are_suppressed(text):
    assert should_suppress_proactive_text(text, forbid_question=False) is True


def test_substantive_short_proactive_reaction_is_not_suppressed():
    assert (
        should_suppress_proactive_text(
            "那就選科幻片。",
            forbid_question=False,
        )
        is False
    )


@pytest.mark.parametrize(
    "text",
    [
        "把剛才那句話還原一下，你的意思是讓我選，對吧？",
        "這句話其實是讓我替你選一部電影。",
        "這句話的意思是把選擇交給我。",
    ],
)
def test_proactive_semantic_rule_explanations_are_suppressed(text):
    assert should_suppress_proactive_text(text, forbid_question=False) is True


@pytest.mark.parametrize(
    "text",
    [
        "盡力這種話，通常是失敗者才會說的藉口吧？",
        "那不過是失敗者的藉口。",
        "這種自以為是的說法真讓人受不了。",
        "你的說法可笑到讓人想笑。",
    ],
)
def test_unprompted_hostile_proactive_lines_are_suppressed(text):
    assert should_suppress_proactive_text(text, forbid_question=False) is True


def test_proactive_prompt_does_not_answer_its_own_question_or_extend_a_bad_anchor():
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="misread-anchor-client",
        conversation_anchor=(
            "角色：動作片、科幻片，還是劇情片？\n"
            "使用者：看你\n"
            "角色：看我的話，你不怕會失望嗎？"
        ),
        output_language="Traditional Chinese (Taiwan)",
    )

    assert "不是使用者意圖正確無誤的證據" in prompt
    assert "不要沿著誤解繼續演下去" in prompt
    assert "不得用「要／不要／是／不是／好」" in prompt
    assert "表示把選擇交給角色，不是凝視角色本人" in prompt
    assert "已判定的省略語修正" in prompt
    assert "立即停止外貌、被觀看、害羞、失望" in prompt
    assert "回到原本的選擇題" in prompt
    assert "不得說成使用者已經選定" in prompt
    assert "不得把原本要做的活動換成另一件事" in prompt


def test_correct_delegated_choice_answer_does_not_trigger_repair_block():
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="correct-choice-anchor-client",
        conversation_anchor=(
            "角色：科幻、動作，還是劇情片？\n"
            "使用者：看你\n"
            "角色：那就科幻片吧，我比較喜歡能認真推演設定的作品。"
        ),
    )

    assert "已判定的省略語修正" not in prompt


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
            "我是牧瀨紅莉棲。人類よ。",
            "Traditional Chinese (Taiwan)",
            protected_names={"紅莉栖": ["紅麗棲", "紅莉棲", "紅麗栖"]},
        )
        == "我是牧瀨紅莉栖。人類。"
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


def test_visual_trigger_requires_a_concrete_grounded_observation():
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="visual-client",
        idle_seconds=10,
        image_sources=["camera", "screen"],
    )

    assert "鏡頭、桌面" in prompt
    assert "先實際檢查圖片" in prompt
    assert "不要捏造" in prompt
    assert "不代表使用者已經選擇、購買、抽中或按下" in prompt
    assert "不同欄位或項目的數字不能自行拼成因果" in prompt
    assert "不得聲稱角色能代替使用者按下、控制或改變介面" in prompt
    assert "至少要帶一個可核對的具體細節" in prompt
    assert "這次只有桌面畫面" not in prompt
    assert "若沒有新資訊，就延續文字話題" in prompt


def test_screen_only_trigger_cannot_invent_the_users_face_or_movement():
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="screen-only-client",
        image_sources=["screen"],
    )

    assert "這次只有桌面畫面" in prompt
    assert "不能聲稱看見使用者的臉、眼神、表情、姿勢或動作" in prompt
    assert "不等於已經證明錯誤原因" in prompt
    assert "編輯器原始碼、終端輸出、網頁文字、通知" in prompt
    assert "不是自動除錯" in prompt
    assert "不得增加尚未發生的動作、結果或感受" in prompt


def test_neutral_visual_pass_is_separate_from_character_persona():
    llm = _FakeVisionFactLLM()
    context = SimpleNamespace(agent_engine=SimpleNamespace(_llm=llm))

    facts = asyncio.run(
        extract_proactive_visual_facts(
            context,
            [
                {
                    "source": "screen",
                    "data": "data:image/jpeg;base64,AAAA",
                    "mime_type": "image/jpeg",
                }
            ],
            "Traditional Chinese (Taiwan)",
        )
    )

    assert facts == "- 編輯器顯示 service_context.py\n- 底部是終端機"
    assert "neutral visual perception stage" in llm.system
    assert llm.messages[0]["content"][1]["type"] == "image_url"


def test_verified_visual_facts_replace_open_ended_image_inference():
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="verified-vision-client",
        image_sources=["screen"],
        verified_visual_facts=(
            "- 主要視窗是 VS Code\n"
            "- 編輯器顯示 service_context.py\n"
            "- 底部終端機有 DEBUG 文字"
        ),
    )

    assert "已驗證的畫面事實" in prompt
    assert "此階段沒有原圖" in prompt
    assert "不得補充清單以外的畫面細節" in prompt
    assert "編輯器顯示 service_context.py" in prompt


def test_trigger_without_images_forbids_pretending_to_see_the_desktop():
    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="text-only-client",
    )

    assert "這一輪沒有畫面" in prompt
    assert "不要假裝看見" in prompt


def test_recent_proactive_window_is_bounded_per_session():
    clear_proactive_context("character", "client")
    for index in range(MAX_RECENT_PROACTIVE + 2):
        record_proactive_response("character", "client", f"第 {index} 句")

    recent = get_recent_proactive("character", "client")

    assert len(recent) == MAX_RECENT_PROACTIVE
    assert recent[0] == "第 2 句"
    assert recent[-1] == f"第 {MAX_RECENT_PROACTIVE + 1} 句"


def test_anchor_extraction_keeps_only_character_turns():
    """The anchor mixes both speakers; only the character's own lines may be
    fed to the duplicate check, and a turn may span several lines."""
    anchor = (
        "使用者：測試測試\n"
        "角色：「測試」這種話，果然又是為了確認我的語音輸出順不順吧？\n"
        "我這邊反應有點延遲，看來是系統剛剛載入的。\n"
        "使用者：那你繼續\n"
        "角色：知道了。"
    )

    assert extract_anchor_character_lines(anchor) == [
        "「測試」這種話，果然又是為了確認我的語音輸出順不順吧？\n"
        "我這邊反應有點延遲，看來是系統剛剛載入的。",
        "知道了。",
    ]
    assert extract_anchor_character_lines(None) == []
    assert extract_anchor_character_lines("使用者：只有使用者講話") == []


def test_proactive_output_copying_the_anchor_is_suppressed():
    """The failure this guards: a small model emits the anchor back verbatim,
    so the proactive turn repeats the reply the user just read."""
    anchor = (
        "使用者：測試測試\n"
        "角色：既然連這種基本功能都要先試一次……你確定接下來要聊些稍微像樣的話題嗎？"
    )
    recent_outputs = extract_anchor_character_lines(anchor)

    assert (
        should_suppress_proactive_text(
            "既然連這種基本功能都要先試一次……你確定接下來要聊些稍微像樣的話題嗎？",
            forbid_question=False,
            recent_outputs=recent_outputs,
        )
        is True
    )
    # Quoting one's own previous phrase back and answering it is the
    # self-interview pattern; it must not survive either.
    assert (
        should_suppress_proactive_text(
            "「稍微像樣的話題」這種說法，聽起來好像你在故意刁難一樣。",
            forbid_question=False,
            recent_outputs=recent_outputs,
        )
        is True
    )
    # A genuine continuation on the same topic still gets through.
    assert (
        should_suppress_proactive_text(
            "剛才那段延遲我查了一下，是模型載入時的冷啟動，第二次就不會了。",
            forbid_question=False,
            recent_outputs=recent_outputs,
        )
        is False
    )


def test_quoting_the_user_is_not_treated_as_self_repetition():
    """Only the character's turns enter the comparison list, so echoing the
    user's own words back stays allowed."""
    anchor = "使用者：我今天把 Live2D 的物理演算調完了\n角色：喔。"

    assert (
        should_suppress_proactive_text(
            "你說的「把 Live2D 的物理演算調完了」，那頭髮的擺動有調到自然嗎？",
            forbid_question=False,
            recent_outputs=extract_anchor_character_lines(anchor),
        )
        is False
    )


def test_anchor_comparison_survives_simplified_traditional_drift():
    """The anchor comes from raw memory and the checked sentence has already
    been normalized, so an exact copy differs only by script variant."""
    anchor = (
        "角色：既然连这种基本功能都要先试一次……你确定接下来要聊些稍微像样的话题吗？"
    )
    language = "Traditional Chinese (Taiwan)"

    raw_lines = extract_anchor_character_lines(anchor)
    normalized_lines = [
        normalize_output_language_variant(line, language) for line in raw_lines
    ]
    checked = normalize_output_language_variant(
        "既然连这种基本功能都要先试一次……你确定接下来要聊些稍微像样的话题吗？",
        language,
    )

    assert (
        should_suppress_proactive_text(
            checked,
            forbid_question=False,
            recent_outputs=raw_lines,
        )
        is False
    ), (
        "without normalization the copy slips through — this is why the handler normalizes"
    )
    assert (
        should_suppress_proactive_text(
            checked,
            forbid_question=False,
            recent_outputs=normalized_lines,
        )
        is True
    )


def test_anchor_is_normalised_before_the_model_reads_it():
    """The anchor comes from memory, which stores what the model produced.

    _add_message applies strip_stage_performance_tag and deduplicate_response_text
    but not normalize_output_language_variant, so a turn that drifted into
    Simplified is remembered that way — while the same turn was displayed, spoken
    and written to history in Traditional. Pasting that back into the prompt shows
    the model its own past turns in the script it is meant to have stopped using.

    Observed in the debug log as one anchor block holding both scripts at once:
    the first sentence Traditional, the rest Simplified.
    """
    mixed = "使用者：測試\n角色：我这边反应有点延迟，看来是系统刚刚加载的。"

    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="anchor-script-client",
        conversation_anchor=mixed,
        output_language="Traditional Chinese (Taiwan)",
    )

    assert "我這邊反應有點延遲" in prompt
    assert "我这边反应有点延迟" not in prompt


def test_anchor_is_left_alone_when_no_language_is_configured():
    """normalize_output_language_variant only converts for Taiwan zh; with no
    configured language the anchor must pass through untouched rather than being
    silently rewritten."""
    anchor = "角色：我这边反应有点延迟。"

    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid="character",
        client_uid="anchor-nolang-client",
        conversation_anchor=anchor,
    )

    assert "我这边反应有点延迟" in prompt


def test_an_identical_short_line_is_suppressed_regardless_of_length():
    """短句會從每一道長度門檻底下溜過去。

    近似比對要求 >=10 字、子句比對 >=6、引述比對 >=4。實測連續三輪主動發言都
    說「別做夢了，哈！」——壓縮後只有 5 個字，三道全部放行，使用者連聽三次
    同一句。說一模一樣的話從來不會是對的，不管它多短。
    """
    previous = ["別做夢了，哈！"]

    assert (
        should_suppress_proactive_text(
            "別做夢了，哈！", forbid_question=False, recent_outputs=previous
        )
        is True
    )


def test_punctuation_only_differences_still_count_as_identical():
    assert (
        should_suppress_proactive_text(
            "別做夢了，哈。", forbid_question=False, recent_outputs=["別做夢了，哈！"]
        )
        is True
    )


def test_a_genuinely_different_short_line_still_gets_through():
    """完全比對不能變成「短句一律擋」——那會讓角色沒辦法講短話。"""
    assert (
        should_suppress_proactive_text(
            "那你想聊什麼？", forbid_question=False, recent_outputs=["別做夢了，哈！"]
        )
        is False
    )
    assert (
        should_suppress_proactive_text(
            "別做夢了！", forbid_question=False, recent_outputs=["別做夢了，哈！"]
        )
        is False
    )


# ---------------------------------------------------------------------------
# 「我說一句結果他一直說」：一句真人發言之後，主動發言連續獨白十幾則。
# 三個獨立缺陷合起來造成的，以下分別鎖住。
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["沒。", "有。", "會。", "不會。", "沒有。", "能。"])
def test_bare_yes_no_proactive_fragments_are_suppressed(text):
    """「沒。」這種裸答案在主動回合沒有對象可答，只會像在自問自答。

    _PROACTIVE_ACKNOWLEDGEMENT_FRAGMENTS 原本收了「要／不要／是／不是／對」，
    卻漏掉同一個家族的「有／沒／沒有／會／不會／能／不能」，實測畫面上出現過
    一顆單獨的「沒。」泡泡。
    """
    assert should_suppress_proactive_text(text, forbid_question=False) is True


def test_negation_words_inside_a_real_sentence_still_pass():
    """裸答案要擋，但含這些字的正常句子不能被連坐。"""
    assert (
        should_suppress_proactive_text(
            "沒有啦，我只是在想剛才那個實驗。", forbid_question=False
        )
        is False
    )


def test_a_real_user_turn_resets_the_proactive_counter():
    """計數本身還在——錨點靠 _since_user 把她這段期間講過的話接上去。

    節流的語意拿掉了（原本連續 3 次就閉嘴），但歸零的時機不能跟著沒了：使用者真的
    開口之後，那段自言自語就不該再被當成「接下來要承接的內容」。
    """
    conf, uid = "character", "budget-reset"
    clear_proactive_context(conf, uid)

    for index in range(3):
        record_proactive_response(conf, uid, f"主動發言第 {index} 則。")
    assert consecutive_proactive_turns(conf, uid) == 3

    note_real_user_turn(conf, uid)

    assert consecutive_proactive_turns(conf, uid) == 0


def test_anchor_advances_with_what_the_character_already_said_proactively():
    """主動回合帶 skip_memory，永遠不進 agent 記憶。

    後果是每一輪拿到的錨點都凍結在同一組真實對話上，而錨點指示又要求
    「必須直接承接其中最後一件具體事情」——於是她一題答十次。錨點必須把
    這段期間自己講過的話按順序接上去，最後一件事才會往前走。
    """
    conf, uid = "character", "anchor-advance"
    clear_proactive_context(conf, uid)
    record_proactive_response(conf, uid, "所以說，想看到背後的東西應該怎麼做呢？")

    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid=conf,
        client_uid=uid,
        conversation_anchor="使用者：你會轉頭嗎\n角色：會啊，不過是脖子自己在動。",
    )

    anchor_block = prompt.split("## 最近真實對話錨點", 1)[1].split("##", 1)[0]
    assert "角色：所以說，想看到背後的東西應該怎麼做呢？" in anchor_block
    assert anchor_block.index("你會轉頭嗎") < anchor_block.index("想看到背後的東西")


def test_anchor_drops_stale_proactive_lines_once_the_user_speaks_again():
    conf, uid = "character", "anchor-advance-reset"
    clear_proactive_context(conf, uid)
    record_proactive_response(conf, uid, "所以說，想看到背後的東西應該怎麼做呢？")
    note_real_user_turn(conf, uid)

    prompt = build_proactive_prompt(
        "基本指令",
        conf_uid=conf,
        client_uid=uid,
        conversation_anchor="使用者：換個話題\n角色：好啊。",
    )

    anchor_block = prompt.split("## 最近真實對話錨點", 1)[1].split("##", 1)[0]
    assert "想看到背後的東西" not in anchor_block


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


def test_idle_trigger_keeps_working_after_many_proactive_turns():
    """連續獨白沒有上限了（使用者要求拿掉）。

    原本卡在 3 次：她連講三次而使用者都沒回，就閉嘴等回覆。那個上限是為了「對著牆
    講話」的情況加的——實測過一句「你會轉頭嗎」後面跟著十幾句自問自答。

    拿掉之後那個風險回來了，但性質已經不同：當時同一句會被重生幾十次，因為被擋掉的
    句子不會進防重複清單（見 record_suppressed_proactive）。現在她至少每次會換一句
    講，而不是撞同一面牆。
    """
    conf, history = "character", "budget-handler"
    clear_proactive_context(conf, history)
    for index in range(10):
        record_proactive_response(conf, history, f"主動發言第 {index} 則。")

    context = _proactive_trigger_context(conf, history)
    websocket = _RecordingWebSocket()
    tasks = {}

    asyncio.run(_run_trigger(context, websocket, idle_time=120, tasks=tasks))

    assert "client" in tasks
    tasks["client"].cancel()


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


def test_a_line_that_only_repeats_the_opening_of_a_previous_one_is_suppressed():
    """實測畫面上連著兩顆泡泡，第二顆逐字就是第一顆的開頭。

    既有三道檢查都是拿「舊句子的子句」去量「新句子」的比例，長舊句 + 短新句
    正好從每一道底下溜過去：子句佔比不足 0.55、近似比對被舊句的長度稀釋。
    """
    previous = (
        "嗯……你這樣說我也沒辦法反對啦，畢竟這就是「一番賞」的玩法嘛。"
        "不過講到模型的話……我倒是想問問你，有試過自己動手拼嗎？"
    )

    assert should_suppress_proactive_text(
        "嗯……你這樣說我也沒辦法反對啦，畢竟這就是「一番賞」的玩法嘛。",
        forbid_question=False,
        recent_outputs=[previous],
    )


def test_a_short_new_sentence_is_not_suppressed_just_for_being_short():
    previous = (
        "嗯……你這樣說我也沒辦法反對啦，畢竟這就是「一番賞」的玩法嘛。"
        "不過講到模型的話……我倒是想問問你，有試過自己動手拼嗎？"
    )

    assert not should_suppress_proactive_text(
        "說起來，桌上那盞燈的角度也太刁鑽了。",
        forbid_question=False,
        recent_outputs=[previous],
    )


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


@pytest.mark.parametrize(
    "text",
    [
        "是不是我的程式碼裡也該加一點點「靈魂」，讓它不再只是冷冰冰的邏輯堆疊。",
        "畢竟我的程式碼可沒你畫出來的東西那麼有靈魂。",
        "別開玩笑了，我只是個 AI。",
        "說到底我不過是程式而已。",
        "我這種人工智慧大概不懂那種感覺吧。",
    ],
)
def test_unprompted_self_as_code_lines_are_suppressed(text):
    """主動發言沒有使用者的問題要答，這種自述必定是自己冒出來的。

    persona 已經逐字禁了「只是個 AI」，9B 照樣講（logs/debug_2026-08-17.log:7185、
    7702）。主動發言這條路有 retry，擋掉直接重生成一次比再加一條散文規則可靠。
    """
    assert should_suppress_proactive_text(text, forbid_question=False) is True


@pytest.mark.parametrize(
    "text",
    [
        "你畫面上那段程式碼的縮排錯了，第三行。",
        "這種模型的程式碼通常會把推理跟輸出分開寫。",
        "AI 生成的圖最近確實進步很多。",
        "我的咖啡涼掉了，重泡一杯。",
    ],
)
def test_talking_about_code_or_ai_as_a_topic_is_not_suppressed(text):
    """她會看著螢幕聊程式碼——禁的是「自稱程式」，不是「談程式」。"""
    assert should_suppress_proactive_text(text, forbid_question=False) is False


@pytest.mark.parametrize(
    "text",
    [
        "說老實話，我是程式設計的門外漢，那段我看不懂。",
        "我是程式語言的使用者，不是它的作者。",
    ],
)
def test_naming_a_field_is_not_calling_yourself_a_program(text):
    """「我是程式設計的門外漢」講的是領域，不是自稱程式。"""
    assert should_suppress_proactive_text(text, forbid_question=False) is False
