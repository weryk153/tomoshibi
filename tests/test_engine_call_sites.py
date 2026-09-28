"""character_engine_agent 在對話流程裡的兩個接點。

跟 test_reply_guidance_not_in_history.py 同一種測法：process_single_conversation
要整條對話鏈才跑得起來，所以盯原始碼裡的呼叫點。這兩個接點拿掉之後其他測試
全部還是綠的（審查抓到的），而功能會無聲地失效。
"""

import inspect

from src.open_llm_vtuber import service_context
from src.open_llm_vtuber.conversations import single_conversation


def hook_call():
    src = inspect.getsource(single_conversation.process_single_conversation)
    assert src.count("notify_turn_finished(") == 1
    return src, src.split("notify_turn_finished(", 1)[1].split(")", 1)[0]


def test_the_engine_is_given_what_the_user_actually_said():
    _, call = hook_call()

    assert "user_text=input_text," in call, (
        "model_input_text 接了防重複提示，那不是使用者講的"
    )
    assert "reply=full_response," in call
    assert "is_proactive=is_proactive," in call


def test_the_turn_is_handed_over_before_waiting_for_the_voice_to_finish():
    """finalize_conversation_turn 會等語音播完。她講話的那十幾秒模型是閒著的，
    背景工作要趁這段時間跑；等播完才交出去的話，背景一開始就碰上下一輪對話。"""
    src, _ = hook_call()

    assert src.index("notify_turn_finished(") < src.index(
        "await finalize_conversation_turn("
    )


def test_the_agent_factory_is_told_which_character_it_is_building_for():
    src = inspect.getsource(service_context.ServiceContext.init_agent)
    create = src.split("AgentFactory.create_agent(", 1)[1]

    assert "conf_uid=target_character.conf_uid," in create
    assert "character_name=target_character.character_name," in create
