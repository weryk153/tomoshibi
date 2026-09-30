"""character_engine_agent 在對話流程裡的接點。

跟 test_reply_guidance_not_in_history.py 同一種測法：process_single_conversation
要整條對話鏈才跑得起來，所以盯原始碼裡的呼叫點。這些接點拿掉之後其他測試全部
還是綠的（審查抓到的），而功能會無聲地失效。
"""

import inspect

from src.open_llm_vtuber import service_context
from src.open_llm_vtuber.conversations import single_conversation


def test_every_call_to_the_agent_names_the_conversation_and_the_users_own_words():
    """agent 是所有連線共用的，主機又在使用者的話後面接了只給模型看的提示。
    重生的那兩條路漏掉的話，引擎會把提示記成使用者說的、記到別段對話裡。"""
    src = inspect.getsource(single_conversation.process_single_conversation)

    assert '"history_uid": context.history_uid' in src
    assert 'agent_metadata["spoken_text"] = input_text' in src
    assert src.count("create_batch_input(") == 3
    assert src.count("metadata=agent_metadata,") == 2
    assert src.count('metadata={**agent_metadata, "redo": True},') == 1


def test_the_agent_factory_is_told_which_character_it_is_building_for():
    src = inspect.getsource(service_context.ServiceContext.init_agent)
    create = src.split("AgentFactory.create_agent(", 1)[1]

    assert "conf_uid=target_character.conf_uid," in create
    assert "character_name=target_character.character_name," in create


def test_a_group_turn_names_the_conversation_of_the_member_who_speaks():
    from src.open_llm_vtuber.conversations import group_conversation

    src = inspect.getsource(group_conversation.handle_group_member_turn)

    assert '"history_uid": member_context.history_uid' in src or (
        '"history_uid": context.history_uid' in src
    )


def test_the_agent_factory_is_told_whether_long_term_memory_is_on():
    src = inspect.getsource(service_context.ServiceContext.init_agent)
    create = src.split("AgentFactory.create_agent(", 1)[1]

    assert (
        "long_term_memory_enabled=target_character.long_term_memory_enabled," in create
    )


def test_a_proactive_turn_hands_the_agent_its_material():
    from src.open_llm_vtuber.conversations import conversation_handler

    src = inspect.getsource(conversation_handler)

    assert "material = proactive_material(user_input)" in src
    assert '"proactive_material": material,' in src
    assert "instruction = proactive_instruction(user_input)" in src
    assert '"proactive_instruction": instruction,' in src
