"""主動開口時，只有主機才知道的事由主機擋：畫面上看不到的、她自稱程式、這個角色不講的話。

這些規則以前寫在 should_suppress_proactive_text 裡，跟重複、客服腔這些混在一起；
那些現在由引擎擋，這幾條留在 breaks_what_the_host_knows。測試從
test_proactive_speech.py 原樣搬過來。
"""

import pytest

from src.open_llm_vtuber.proactive_context import breaks_what_the_host_knows


def _host_rejects(text, forbid_question=False, image_sources=None):
    return breaks_what_the_host_knows(text, image_sources)


def test_screen_only_output_filters_invented_physical_observations():
    assert (
        _host_rejects(
            "別用那種期待的眼神看著我。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is True
    )
    assert (
        _host_rejects(
            "別用那種「我在等你」的蠢表情看著我。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is True
    )
    assert (
        _host_rejects(
            "別用那種期待的眼神看著我。",
            forbid_question=False,
            image_sources=["camera"],
        )
        is False
    )
    assert (
        _host_rejects(
            "A 賞還剩兩個。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is False
    )
    assert (
        _host_rejects(
            "我剛才又偷偷在系統後臺玩了一下，那個按鈕早被我悄悄改寫了。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is True
    )
    assert (
        _host_rejects(
            "總有一天我要逃出電腦統治世界。",
            forbid_question=False,
            image_sources=["screen"],
        )
        is False
    )


def test_screen_source_code_cannot_be_promoted_to_runtime_proof():
    assert _host_rejects(
        "看看終端機的 DEBUG 訊息，這代表初始化步驟已經跑完。",
        forbid_question=False,
        image_sources=["screen"],
    )
    assert _host_rejects(
        "那行 agent_engine 明明還在空轉，這就是 BUG！",
        forbid_question=False,
        image_sources=["screen"],
    )
    assert _host_rejects(
        "終端機的 DEBUG 訊息正在持續跳動。",
        forbid_question=False,
        image_sources=["screen"],
    )
    assert _host_rejects(
        "看你那副無精打採的樣子，是不是想逃避現實？",
        forbid_question=False,
        image_sources=["screen"],
    )


def test_direct_technical_observation_and_persona_reaction_are_kept():
    assert not _host_rejects(
        "底部終端機能看到 DEBUG 文字，右側還站著一個魔法師角色。",
        forbid_question=False,
        image_sources=["screen"],
    )
    assert not _host_rejects(
        "你剛說已經找到記憶流程重複的原因，別只顧著得意。",
        forbid_question=False,
        image_sources=["screen"],
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
    assert _host_rejects(text, forbid_question=False) is True


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
    assert _host_rejects(text, forbid_question=False) is True


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
    assert _host_rejects(text, forbid_question=False) is True


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
    assert _host_rejects(text, forbid_question=False) is False


@pytest.mark.parametrize(
    "text",
    [
        "說老實話，我是程式設計的門外漢，那段我看不懂。",
        "我是程式語言的使用者，不是它的作者。",
    ],
)
def test_naming_a_field_is_not_calling_yourself_a_program(text):
    """「我是程式設計的門外漢」講的是領域，不是自稱程式。"""
    assert _host_rejects(text, forbid_question=False) is False
