"""character_engine_agent 在對話流程裡的接點。

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


def test_every_call_to_the_agent_names_the_conversation_and_the_users_own_words():
    """agent 是所有連線共用的，主機又在使用者的話後面接了只給模型看的提示。
    重生的那兩條路漏掉的話，引擎會把提示記成使用者說的、記到別段對話裡。"""
    src = inspect.getsource(single_conversation.process_single_conversation)

    assert '"history_uid": context.history_uid' in src
    assert 'agent_metadata["spoken_text"] = input_text' in src
    assert src.count("create_batch_input(") == 3
    assert src.count("metadata=agent_metadata,") == 3


def test_the_turn_is_handed_over_before_waiting_for_the_voice_to_finish():
    """finalize_conversation_turn 會等語音播完。使用者在她講話中途又開口的話，
    下一輪她讀到的就還是主機修過之前的那一版回覆。"""
    src, _ = hook_call()

    assert src.index("notify_turn_finished(") < src.index(
        "await finalize_conversation_turn("
    )


def test_the_agent_factory_is_told_which_character_it_is_building_for():
    src = inspect.getsource(service_context.ServiceContext.init_agent)
    create = src.split("AgentFactory.create_agent(", 1)[1]

    assert "conf_uid=target_character.conf_uid," in create
    assert "character_name=target_character.character_name," in create
