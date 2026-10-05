"""口頭禪的兩個純函式：一句話是不是只有口頭禪、把口頭禪換成目標寫法。

一句話只有口頭禪（例如「konpeko！」）時，不必、也不該送去翻譯模型：模型會把
它音譯成「孔佩可」或「コンペコ」。照角色設定的寫法直接換掉就好。
"""

from src.open_llm_vtuber.translate.catchphrases import (
    only_catchphrases,
    replace_catchphrases,
)

PEKO = {"peko": "ぺこ", "konpeko": "こんぺこ", "otsupeko": "おつぺこ"}


def test_a_lone_catchphrase_with_punctuation_is_only_catchphrases():
    assert only_catchphrases("konpeko！", PEKO)
    assert only_catchphrases("  konpeko!  ", PEKO)
    assert only_catchphrases("Konpeko~", PEKO)


def test_several_catchphrases_together_are_only_catchphrases():
    assert only_catchphrases("konpeko, peko!", PEKO)
    assert only_catchphrases("OTSUPEKO…ぺこ？", {**PEKO, "ぺこ": "ぺこ"})


def test_a_sentence_with_other_words_is_not_only_catchphrases():
    assert not only_catchphrases("konpeko！大家好", PEKO)
    assert not only_catchphrases("要叫「konpeko」才是打招呼的方式!", PEKO)
    assert not only_catchphrases("konpeko 3", PEKO)


def test_latin_keys_match_whole_words_only():
    # 「pekora」裡的 peko 不是口頭禪。
    assert not only_catchphrases("pekora!", PEKO)
    assert replace_catchphrases("pekora peko", PEKO) == "pekora ぺこ"


def test_no_keys_or_no_catchphrase_is_not_only_catchphrases():
    assert not only_catchphrases("konpeko！", {})
    assert not only_catchphrases("！？", PEKO)
    assert not only_catchphrases("", PEKO)


def test_replace_uses_the_target_form_and_keeps_punctuation():
    assert replace_catchphrases("konpeko！", PEKO) == "こんぺこ！"
    assert replace_catchphrases("Konpeko, peko!", PEKO) == "こんぺこ, ぺこ!"
    assert replace_catchphrases("otsupeko～", PEKO) == "おつぺこ～"


def test_replace_next_to_cjk_text_still_matches():
    assert replace_catchphrases("要叫konpeko才對", PEKO) == "要叫こんぺこ才對"


def test_non_latin_keys_match_as_substrings_longest_first():
    mapping = {"にゃ": "nya", "にゃん": "nyan"}
    assert replace_catchphrases("にゃん！にゃ", mapping) == "nyan！nya"
    assert only_catchphrases("にゃんにゃ！", mapping)


def test_replace_with_no_mapping_returns_the_text_unchanged():
    assert replace_catchphrases("konpeko！", {}) == "konpeko！"
