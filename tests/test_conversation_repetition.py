from src.open_llm_vtuber.conversation_quality import (
    CORE_CONVERSATION_PROMPT,
    ResponseRepetitionGuard,
    deduplicate_response_text,
    is_repetitive_response_segment,
)


def test_exact_and_lightly_reworded_sentences_are_repetitive():
    previous = ["我覺得這個方法很好。"]

    assert is_repetitive_response_segment("我覺得這個方法很好！", previous)
    assert is_repetitive_response_segment("我覺得這個方法很不錯。", previous)


def test_changed_fact_or_polarity_is_preserved():
    previous = ["畫面目前還剩 67 張。", "我喜歡這個方法。"]

    assert not is_repetitive_response_segment("畫面目前還剩 66 張。", previous)
    assert not is_repetitive_response_segment("我不喜歡這個方法。", previous)


def test_new_detail_is_not_mistaken_for_a_repeat():
    previous = ["我喜歡紅茶的麥芽香。"]

    assert not is_repetitive_response_segment(
        "冬天喝熱紅茶也能讓手暖起來。",
        previous,
    )


def test_guard_only_records_accepted_segments():
    guard = ResponseRepetitionGuard()

    assert guard.accept("這個方法很適合目前的情況。")
    assert not guard.accept("這個方法很適合現在的情況。")
    assert guard.accept("下一步可以先保存設定。")


def test_memory_text_drops_repeated_sentence_and_ignores_control_tags():
    response = "[smirk]這個方法很好。 [neutral]這個方法很好！接著保存設定。"

    assert deduplicate_response_text(response) == (
        "[smirk]這個方法很好。接著保存設定。"
    )


def test_core_prompt_keeps_the_rule_that_no_code_enforces():
    """跨輪複述沒有任何程式碼在管。

    ResponseRepetitionGuard 只作用於同一輪的串流內，deduplicate_response_text
    只作用於單則文字內。這條規則一旦從常駐層拿掉就沒有第二道防線。
    """
    assert "paraphrase your immediately preceding reply" in CORE_CONVERSATION_PROMPT
    assert "generic assistant sign-offs" in CORE_CONVERSATION_PROMPT


def test_core_prompt_is_the_pre_refactor_text_verbatim():
    """常駐層與重構前逐位元組相同——這是人讀 135 則回覆後的判定，不是猜的。

    這裡曾經有一道 < 1200 字的上限，前提是「超過一半的規則已在別處」。機械上
    那個分析是對的（turn-local 提示與事後過濾確實覆蓋同樣的規則），但三個版本
    （4143／3646／540）各跑 3 次、135 則回覆並排給使用者判讀後，結論是完整
    舊版最像角色。自動化指標在 temperature 0.7 下的 run-to-run 變異蓋過版本
    差異，不足以支持任何瘦身。要重新嘗試壓縮之前，先做多次重複的人讀對照，
    不要只看規則有沒有在別處出現。

    從前這裡是去 git show 一個 commit 取出當時的原文。那綁死了 repo 的歷史，
    換一份歷史就整個崩掉——而且它讀的是版本庫，不是隨程式碼一起發佈的東西。
    改成比對 tests/data 裡的 golden 檔：內容就是當初那個 commit 逐位元組取出
    的原文，只是現在跟著程式碼一起走。要改這段提示詞，得連 golden 一起改，
    那正是本測試要求的「刻意」。
    """
    from pathlib import Path as _Path

    golden = _Path(__file__).parent / "data" / "core_conversation_prompt.golden.txt"
    assert CORE_CONVERSATION_PROMPT == golden.read_text(encoding="utf-8")
