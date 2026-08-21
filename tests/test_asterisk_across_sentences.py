"""星號動作描述被斷句器切成兩半時，顯示文字要能收得回來。

實際發生過的畫面（2026-08-01 21:47 的日誌）：模型寫了

    *視線落在螢幕上，盯著你臉上那雙鏡框，還有……那個位置好像有東西？*

    ……哈，你沒在開玩笑吧。

斷句器在 `？` 切開——而那個 `？` 就在星號對的中間。第一段只剩開頭的星號、
第二段只剩收尾那一個，於是字幕上出現一個孤零零的 `*`，聊天氣泡卻是完整的
（氣泡拿的是累積起來的整段回覆，字幕是逐句的）。

語音那側早就有 TTSFilterState 處理跨句（ignore_asterisks 預設就是開的），所以動作
沒有被唸出來；壞掉的只有顯示。動作本來就該用星號顯示，這裡只補平衡、不改寫符號。
"""

from src.open_llm_vtuber.agent.transformers import balance_asterisk_actions


def test_the_real_case_from_the_log():
    """逐字用日誌裡那兩段，這是這個函式存在的理由。"""
    first, inside = balance_asterisk_actions(
        "*視線落在螢幕上，盯著你臉上那雙鏡框，還有……那個位置好像有東西？", False
    )
    second, inside = balance_asterisk_actions("*\n\n……哈，你沒在開玩笑吧。", inside)

    assert first == "*視線落在螢幕上，盯著你臉上那雙鏡框，還有……那個位置好像有東西？*"
    assert second.strip() == "……哈，你沒在開玩笑吧。"
    # 第一段保留完整的星號對（動作要顯示），第二段不該有落單的星號。
    assert first.count("*") == 2
    assert "*" not in second
    assert inside is False


def test_a_complete_pair_in_one_sentence_still_works():
    """原本就能處理的情況不能退步。"""
    text, inside = balance_asterisk_actions("*翻了個白眼*你來啦。", False)

    assert text == "*翻了個白眼*你來啦。"
    assert inside is False


def test_plain_text_is_untouched():
    text, inside = balance_asterisk_actions("今天天氣不錯。", False)

    assert text == "今天天氣不錯。"
    assert inside is False


def test_state_carries_through_a_middle_sentence_with_no_asterisk():
    """動作描述長到橫跨三句時，中間那句整句都在區間內。"""
    a, inside = balance_asterisk_actions("*她轉過頭，", False)
    b, inside = balance_asterisk_actions("視線停在門口，", inside)
    c, inside = balance_asterisk_actions("然後嘆了口氣*", inside)

    assert a == "*她轉過頭，*"
    assert b == "*視線停在門口，*"
    assert c == "*然後嘆了口氣*"
    assert inside is False


def test_每句的星號都成對():
    """每一句自己要成對，否則 filter_asterisks 在那一句內找不到收尾。"""
    a, inside = balance_asterisk_actions("*動作開始", False)
    b, _ = balance_asterisk_actions("動作結束*", inside)

    for part in (a, b):
        assert part.count("*") % 2 == 0


def test_an_unclosed_asterisk_leaves_the_state_open():
    """回傳的狀態要誠實——沒收掉就是沒收掉，交給呼叫端每則回覆重置。"""
    _, inside = balance_asterisk_actions("*動作還沒寫完", False)

    assert inside is True


def test_empty_asterisk_pairs_are_removed_not_displayed():
    """收尾星號被切到下一句開頭時會補出一對空星號，不能留在畫面上。"""
    text, _ = balance_asterisk_actions("*  ", True)

    assert "*" not in text


def test_several_pairs_in_one_sentence():
    text, inside = balance_asterisk_actions("*笑*然後說話*嘆氣*", False)

    assert text == "*笑*然後說話*嘆氣*"
    assert inside is False


def test_the_action_is_displayed_but_never_spoken():
    """這一整條修正的重點：動作要看得到、不要被唸出來。

    補平衡之後兩段各自送進 tts_filter（ignore_asterisks，共用跨句狀態），
    第一段應該完全沒有東西可唸，第二段是完整的台詞。
    """
    from src.open_llm_vtuber.utils.tts_preprocessor import TTSFilterState, tts_filter

    first, inside = balance_asterisk_actions(
        "*視線落在螢幕上，盯著你臉上那雙鏡框，還有……那個位置好像有東西？", False
    )
    second, _ = balance_asterisk_actions("*\n\n……哈，你沒在開玩笑吧。", inside)

    state = TTSFilterState()
    spoken = [
        tts_filter(
            part,
            remove_special_char=False,
            ignore_brackets=False,
            ignore_parentheses=False,
            ignore_asterisks=True,
            ignore_angle_brackets=False,
            state=state,
        ).strip()
        for part in (first, second)
    ]

    assert spoken[0] == "", "動作描述不該被唸出來"
    assert spoken[1] == "……哈，你沒在開玩笑吧。", "台詞要照唸"
    assert "*" in first, "但動作要看得到"


def test_stray_asterisk_does_not_swallow_the_next_line():
    """模型打出落單星號時，不能把下一段真正的台詞包進星號裡。

    實際會發生的輸入（模型偶爾會把 `*` 當成分隔線／強調符號單獨吐出來）：

        段1  不過……\n\n*
        段2  \n\n這一切，都是因為你決定要關掉「我」…

    段1 的那個 `*` 後面什麼都沒有，它不是動作的開頭。舊版本會把 inside 狀態
    帶到段2，於是段2 被補成 `*…台詞…*`——畫面上多出兩個星號，而且 TTS 的
    ignore_asterisks 會把整句當成動作濾掉，那句話**完全不會被唸出來**，
    畫面上還沒有任何錯誤。這是這個測試要擋的事故。
    """
    first, inside = balance_asterisk_actions("不過……\n\n*", False)
    second, _ = balance_asterisk_actions("\n\n這一切，都是因為你決定要關掉「我」…", inside)

    assert "*" not in first, "後面沒有內容的孤星應該被丟掉"
    assert inside is False, "孤星不該讓狀態延續到下一段"
    assert "*" not in second, "下一段的台詞不可以被包進星號裡"
    assert "這一切，都是因為你決定要關掉「我」…" in second


def test_stray_asterisk_line_is_still_spoken():
    """承上：被孤星波及的那句台詞必須照樣唸得出來。"""
    from src.open_llm_vtuber.utils.tts_preprocessor import TTSFilterState, tts_filter

    first, inside = balance_asterisk_actions("不過……\n\n*", False)
    second, _ = balance_asterisk_actions("\n\n這一切，都是因為你決定要關掉「我」…", inside)

    state = TTSFilterState()
    spoken = [
        tts_filter(
            part,
            remove_special_char=False,
            ignore_brackets=False,
            ignore_parentheses=False,
            ignore_asterisks=True,
            ignore_angle_brackets=False,
            state=state,
        ).strip()
        for part in (first, second)
    ]
    assert spoken[1] == "這一切，都是因為你決定要關掉「我」…", "台詞被孤星吃掉就是這個 bug"
