"""對話不得由 assistant 起頭——某些 chat template 會整個拒絕。

角色會先開口打招呼，所以只要有歷史，送給 LLM 的訊息第一則就是 assistant。
LM Studio 上 `qwen/qwen3.5-9b` 的 jinja 樣板遇到這個形狀會整個請求失敗：

    Error rendering prompt with jinja template: "No user query found in messages."

對使用者顯示成沒頭沒尾的「Error calling the chat endpoint」。

實測隔離出來的觸發條件（對真實模型逐一送出比對）：
    [system, assistant, user]                  → 失敗
    [system, assistant, sys, user, ai, user]   → 失敗
    [system, user, assistant, user]            → 成功
所以問題**只**在「第一個 user 之前出現 assistant」。中間插入的 system 訊息與
OpenAI 的 content 片段陣列都被接受，兩者都不是原因。
"""

from src.open_llm_vtuber.agent.stateless_llm.openai_compatible_llm import (
    _drop_leading_assistant_turns,
)


def test_drops_the_opening_greeting():
    messages = [
        {"role": "assistant", "content": "嗨"},
        {"role": "user", "content": "你好"},
    ]
    assert _drop_leading_assistant_turns(messages) == [
        {"role": "user", "content": "你好"}
    ]


def test_keeps_a_leading_system_message():
    # 樣板本來就預期 system 在最前面，不能連它一起砍掉。
    messages = [
        {"role": "system", "content": "你是一個角色"},
        {"role": "assistant", "content": "嗨"},
        {"role": "user", "content": "你好"},
    ]
    assert _drop_leading_assistant_turns(messages) == [
        {"role": "system", "content": "你是一個角色"},
        {"role": "user", "content": "你好"},
    ]


def test_preserves_assistant_turns_after_the_first_user_turn():
    # 只丟開場白。真正的來回一則都不能少，否則模型會失去脈絡。
    messages = [
        {"role": "assistant", "content": "開場白"},
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "回覆"},
        {"role": "user", "content": "第二句"},
    ]
    assert _drop_leading_assistant_turns(messages) == [
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "回覆"},
        {"role": "user", "content": "第二句"},
    ]


def test_drops_several_leading_assistant_turns():
    messages = [
        {"role": "assistant", "content": "一"},
        {"role": "assistant", "content": "二"},
        {"role": "user", "content": "你好"},
    ]
    assert _drop_leading_assistant_turns(messages) == [
        {"role": "user", "content": "你好"}
    ]


def test_leaves_an_already_valid_conversation_untouched():
    messages = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "嗨"},
    ]
    assert _drop_leading_assistant_turns(messages) == messages


def test_leaves_a_conversation_with_no_user_turn_alone():
    # 沒有 user 可以當錨點時不要自作主張清空——寧可讓上游看到原始資料。
    messages = [{"role": "assistant", "content": "嗨"}]
    assert _drop_leading_assistant_turns(messages) == messages


def test_keeps_content_part_arrays_intact():
    # content 片段陣列不是問題來源（實測模型接受），不得被改寫。
    parts = [{"type": "text", "text": "你好吵"}]
    messages = [
        {"role": "assistant", "content": "開場白"},
        {"role": "user", "content": parts},
    ]
    assert _drop_leading_assistant_turns(messages) == [
        {"role": "user", "content": parts}
    ]


def test_does_not_mutate_the_input_list():
    messages = [
        {"role": "assistant", "content": "開場白"},
        {"role": "user", "content": "你好"},
    ]
    before = list(messages)
    _drop_leading_assistant_turns(messages)
    assert messages == before
