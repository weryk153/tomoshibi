"""中文版表情提示詞：一則回覆最多一個關鍵字，寫在最後單獨一行。

原本的英文版說 "use them regularly"，實測 313 則回覆裡關鍵字出現 0 次。她連別條
規則也在略過（動作被寫在 <think> 標籤外，那是規則 1 明文禁止的），所以問題不只是
規則打架，還有位置與語言：人設是 2500 字寫得很硬的中文，唯一叫她用方括號的那段
是英文、夾在中間、語氣泛泛。改「嗯」開頭那條之所以有效，就是因為用中文寫死並附了
改寫對照。

「最多一個、放最後」不是保守起見，是兩個副作用的解法：

- 用過頭跟人設打架。芙莉蓮的核心是平淡、反應慢，每句換一次表情不像她。
- 這是全域設定（tool_prompts 在 system_config），mao_pro 也吃得到，所以規則要對
  任何角色都成立。

成本上這個形狀是免費的，實測過：只有標籤的片段，tts 文字濾完是空的，
tts_manager 走靜音 payload——表情照樣送到前端，合成與翻譯都跳過。
"""

from pathlib import Path

PROMPT = Path("prompts/utils/live2d_expression_prompt_zh.txt")


def _text() -> str:
    return PROMPT.read_text(encoding="utf-8")


def test_keeps_the_placeholder_the_loader_substitutes():
    # service_context 用字面 [<insert_emomap_keys>] 做取代。少了它不會報錯，
    # 只會安靜地送出一份沒有任何關鍵字的提示詞。
    assert "[<insert_emomap_keys>]" in _text()


def test_caps_it_at_one_per_reply():
    assert "最多一個" in _text()


def test_says_to_put_it_at_the_front():
    """位置決定看不看得見，不是決定成不成本。

    第一版寫的是「放在整則回覆的最後，單獨一行」——動機是成本：只有標籤的片段
    tts 濾完是空的，tts_manager 走靜音 payload，不合成也不翻譯。實測 30 個標籤裡
    有 27 個確實照做了。

    然後表情一次都沒被看見。因為那個靜音 payload 是回覆的最後一段：表情設下去，
    緊接著 send_conversation_end_signal 讓前端 aiState 變 IDLE，而 live2d.tsx 在
    IDLE 時會 resetExpression()。設下去到被清掉之間只有幾毫秒。

    放最前面一樣免費（'[joy] 這樣就好了吧。' 是一整段，不會多切一次 TTS），而且
    表情會撐過整段話。
    """
    text = _text()

    assert "寫在整則回覆的最前面" in text
    # 提示詞裡還是會提到「最後」——說明為什麼不能那樣寫、以及錯誤範例。
    # 釘的是那條規則本身，不是這兩個字。
    assert "寫在整則回覆的最後" not in text


def test_says_most_replies_should_have_none():
    # 沒有這句，「最多一個」會被讀成「每則都要有一個」。
    assert "不寫" in _text()


def test_does_not_tell_it_to_use_them_regularly():
    # 英文版的 "use them regularly" 正是造成濫用風險的那句，中文版不能把它翻進來。
    assert "經常" not in _text()
