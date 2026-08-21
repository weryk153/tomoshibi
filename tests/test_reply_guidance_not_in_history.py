"""防重複提示只給模型，不能寫進對話歷史。

input_text 同時是「送進模型的東西」和「存進歷史的東西」。把提示直接接在
input_text 上最省事，但那段文字會永久留在 chat_history 裡，之後又被長期記憶
讀走——使用者的對話記錄會混進系統指示，而且看起來像是他自己打的。

這條測試盯的是那個分岔：store_message 拿到的必須是使用者原話。
"""

import inspect

from src.open_llm_vtuber.conversations import single_conversation


def test_store_message_receives_the_raw_user_text():
    src = inspect.getsource(single_conversation.process_single_conversation)
    # 送進模型的是加工過的版本
    assert "input_text=model_input_text" in src
    # 存進歷史的是原話
    store_call = src.split("store_message(", 1)[1]
    assert "content=input_text," in store_call, "歷史必須存使用者原話，不是加工後的"


def test_guidance_is_only_added_for_normal_replies():
    src = inspect.getsource(single_conversation.process_single_conversation)
    guidance_block = src.split("model_input_text = input_text", 1)[1][:400]
    # 主動發言有自己的一套（proactive_context），兩層疊上去會互相打架
    assert "not is_proactive" in guidance_block
