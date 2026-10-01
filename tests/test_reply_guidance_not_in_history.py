"""對話歷史存的是使用者原話，送給 agent 的也是原話。

以前送進模型的是接了「你最近說過這些」提示的加工版，歷史存原話；那段提示隨舊
agent 拿掉了，兩邊現在是同一份——但歷史必須是原話這件事不變。
"""

import inspect

from src.open_llm_vtuber.conversations import single_conversation


def test_history_and_the_agent_both_get_the_raw_user_text():
    src = inspect.getsource(single_conversation.process_single_conversation)
    store_call = src.split("store_message(", 1)[1]
    assert "content=input_text," in store_call
    assert "input_text=input_text," in src
