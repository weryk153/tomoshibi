"""翻譯路徑要保留角色的口頭禪，而且不能影響沒有口頭禪的角色。

音訊翻譯器逐句翻譯時，句尾的口頭禪（例如中文裡的「peko」）常被當贅字丟掉——
它不是一般詞彙，翻譯模型沒有理由保留。這份測試確保：沒設口頭禪時 prompt 跟
加這個功能之前逐字相同（critical：不能影響任何其他角色），設了就把對照表
交代給模型。
"""

from src.open_llm_vtuber.translate.llm_translate import LLMTranslate

# 加這個功能之前，_system_prompt() 在沒有 protected_names 時回傳的字串。
# 用來證明 catchphrases 是空的時候完全不影響既有行為。
_OLD_PROMPT_NO_PROTECTED_NAMES = (
    "You are a deterministic dialogue subtitle translator. Translate the "
    "source into 日文. Translate faithfully, sentence by "
    "sentence. Preserve every fact, subject, pronoun, name, number, negation, "
    "uncertainty, causal relationship, and logical relationship exactly. "
    "Never add, omit, explain, embellish, correct, or invert meaning. Keep the "
    "speaker in first person when the source is first person. Use natural spoken "
    "wording in the target language. Output only the translation "
    "itself, with no preface, commentary, romanization, or surrounding quotation "
    "marks. Preserve quotation marks that belong to quoted terms in the source."
)


def _translator(catchphrases=None, target_lang="日文") -> LLMTranslate:
    return LLMTranslate(
        api_endpoint="http://translator.test/v1/chat/completions",
        model="local-model",
        target_lang=target_lang,
        extra_body={"reasoning_effort": "none"},
        timeout=17,
        catchphrases=catchphrases,
    )


def test_empty_catchphrases_leaves_the_prompt_byte_identical():
    """沒設口頭禪時，prompt 要跟加這個功能之前逐字一樣——不能影響其他角色。"""
    prompt = _translator()._system_prompt()

    assert prompt == _OLD_PROMPT_NO_PROTECTED_NAMES
    assert "catchphrase" not in prompt.lower()


def test_default_constructor_also_leaves_the_prompt_untouched():
    """連 catchphrases 參數都不傳時（呼叫端用舊的方式建構）行為也不變。"""
    translator = LLMTranslate(
        api_endpoint="http://translator.test/v1/chat/completions",
        model="local-model",
        target_lang="日文",
    )

    assert translator.catchphrases == {}
    assert "catchphrase" not in translator._system_prompt().lower()


def test_set_catchphrases_appends_the_mapping_sentence():
    """設了口頭禪，就在 prompt 後面交代對照表，不能動到前面已經有的句子。"""
    prompt = _translator({"peko": "ぺこ"})._system_prompt()

    assert prompt.startswith(_OLD_PROMPT_NO_PROTECTED_NAMES)
    appended = prompt[len(_OLD_PROMPT_NO_PROTECTED_NAMES) :]
    assert "peko" in appended
    assert "ぺこ" in appended
    assert "drop" in appended.lower()


def test_multiple_catchphrases_all_appear():
    prompt = _translator({"peko": "ぺこ", "nyan": "にゃん"})._system_prompt()

    assert "peko" in prompt and "ぺこ" in prompt
    assert "nyan" in prompt and "にゃん" in prompt
