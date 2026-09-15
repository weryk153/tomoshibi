"""核心記憶抽取提示詞：每條記憶都要有明確主詞。

實際發生過的事：芙莉蓮回答「費倫跟修塔爾克應該會先去北方，我可能就跟著他們
走」之後，core_memory.md 出現了

    使用者目前正計畫跟隨費倫與修塔爾克前往北方較遠的地方。
    使用者打算沿途研究新事物，偏好研究看似無用的魔法。
    使用者對漫無目的地研究感到自責。

三條全是角色自己講的話，被記成使用者的事實。舊提示詞其實有寫「絕不記 AI 自己
說的話」，但同一份規則又要求記「重要事件或對話結論」——而那輪的結論正好出自
AI。更根本的是整份記憶被框成「關於使用者的長期記憶」，角色自己的事實沒有欄位
可放，只能被硬塞進使用者的主詞。

所以修法不是再加一條禁令，而是把框架改成兩類、並要求每條寫明主詞。
"""

from src.open_llm_vtuber.memory_core import SELF_CAP_CHARS, build_consolidation_prompt


def test_uses_the_character_name_as_the_subject_label():
    prompt = build_consolidation_prompt(
        current="",
        user_input="去哪",
        ai_response="費倫跟修塔爾克應該會先去北方。",
        cap=1500,
        character_name="芙莉蓮",
    )
    assert "芙莉蓮" in prompt


def test_falls_back_to_a_generic_label_without_a_name():
    # character_name 是可選欄位（預設空字串），沒有名字時不能生出「」這種空殼，
    # 否則提示詞會出現「每條都要以「」或使用者開頭」這種讀不懂的句子。
    prompt = build_consolidation_prompt(
        current="", user_input="嗨", ai_response="嗨。", cap=1500, character_name=""
    )
    assert "「」" not in prompt
    assert "角色" in prompt


def test_carries_the_turn_and_the_existing_memory():
    prompt = build_consolidation_prompt(
        current="使用者叫小明。",
        user_input="今天好累",
        ai_response="辛苦了。",
        cap=800,
        character_name="芙莉蓮",
    )
    assert "使用者叫小明。" in prompt
    assert "今天好累" in prompt
    assert "辛苦了。" in prompt
    # 兩個上限分開講（見 test_self_memory_classify 的同名測試）：合計上限會讓
    # 模型以為對話記憶那半能寫到 cap + self_cap，而 _acceptable_rewrite 對那一半
    # 是用 int(cap * 1.5) 拒收，模型照著寫出來的東西反而被丟掉。
    assert str(800) in prompt
    assert str(SELF_CAP_CHARS) in prompt
    assert str(800 + SELF_CAP_CHARS) not in prompt


def test_says_the_character_statements_must_not_become_user_facts():
    # 這是整個修正的重點，用一個穩定的關鍵詞釘住，避免日後有人改寫提示詞時
    # 把這條規則整段刪掉而沒人發現。
    prompt = build_consolidation_prompt(
        current="",
        user_input="去哪",
        ai_response="往北。",
        cap=1500,
        character_name="芙莉蓮",
    )
    assert "主詞" in prompt


def test_empty_existing_memory_has_no_placeholder_text():
    # 佔位文字「（目前還沒有任何記憶）」拿掉了：它是模型照抄回輸出的來源，三輪
    # 實測裡多次被原樣或近乎原樣回顯進整理結果。空的時候標籤下方直接留空。
    prompt = build_consolidation_prompt(
        current="",
        user_input="嗨",
        ai_response="嗨。",
        cap=1500,
        character_name="芙莉蓮",
    )
    assert "（目前還沒有任何記憶）" not in prompt
