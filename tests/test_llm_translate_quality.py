"""Regression tests for the display-only LLM subtitle translator."""

from __future__ import annotations

from dataclasses import dataclass

from src.open_llm_vtuber.translate.llm_translate import LLMTranslate


@dataclass
class _Response:
    content: str

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self.content}}]}


def _translator(target: str = "繁體中文", protected_names=None) -> LLMTranslate:
    return LLMTranslate(
        protected_names=protected_names,
        api_endpoint="http://translator.test/v1/chat/completions",
        model="local-model",
        target_lang=target,
        extra_body={"reasoning_effort": "none"},
        timeout=17,
    )


def test_translation_uses_a_strict_system_message(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return _Response("這是譯文")

    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post", fake_post
    )

    result = _translator().translate("これは原文です。")

    assert result == "這是譯文"
    assert len(calls) == 1
    url, payload, timeout = calls[0]
    assert url == "http://translator.test/v1/chat/completions"
    assert timeout == 17
    assert payload["temperature"] == 0
    assert payload["reasoning_effort"] == "none"
    assert payload["messages"][0]["role"] == "system"
    assert "Preserve every fact" in payload["messages"][0]["content"]
    assert "never output Simplified Chinese" in payload["messages"][0]["content"]
    assert payload["messages"][1] == {
        "role": "user",
        "content": "これは原文です。",
    }


def test_traditional_subtitles_are_normalized_after_model_output(monkeypatch):
    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post",
        lambda *args, **kwargs: _Response("听起来很重要，但不懂什么意思。"),
    )

    assert _translator().translate("重要に聞こえる。") == (
        "聽起來很重要，但不懂什麼意思。"
    )


def test_untranslated_kana_in_chinese_subtitle_retries_once(monkeypatch):
    responses = iter(
        [
            _Response("結論から言えば，絕對反對。"),
            _Response("結論來說，我絕對反對。"),
        ]
    )
    calls = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return next(responses)

    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post", fake_post
    )

    assert _translator().translate("結論から言うと、絶対反対だ。") == (
        "結論來說，我絕對反對。"
    )
    assert len(calls) == 2
    assert calls[1]["messages"][0]["role"] == "user"
    assert "不得保留任何日文語法或假名" in calls[1]["messages"][0]["content"]
    assert "結論から言うと" in calls[1]["messages"][0]["content"]


def test_japanese_target_that_came_back_in_english_retries_once(monkeypatch):
    # 本機 9B 模型偶爾把中→日翻成英文（實測 395 句有 3 句）；GPT-SoVITS 設成日文
    # 就照英文唸出來。沒有半個假名就是沒翻成日文。
    responses = iter(
        [
            _Response("Since you're so casual, I'll teach you how to say please!"),
            _Response("そんなに適当なら、「お願い」の言い方を教えてあげるぺこ！"),
        ]
    )
    calls = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return next(responses)

    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post", fake_post
    )

    assert _translator("日文").translate(
        "既然你這麼隨便，那就教你一句「拜託」吧！"
    ) == ("そんなに適当なら、「お願い」の言い方を教えてあげるぺこ！")
    assert len(calls) == 2
    assert calls[1]["messages"][0]["role"] == "system"
    assert "not Japanese" in calls[1]["messages"][1]["content"]
    assert "既然你這麼隨便" in calls[1]["messages"][1]["content"]


def test_japanese_target_still_not_japanese_after_retry_falls_back_to_source(
    monkeypatch,
):
    responses = iter(
        [
            _Response("Shall we talk about something relaxing?"),
            _Response("Let's talk about something relaxing instead."),
        ]
    )

    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post",
        lambda url, json, timeout: next(responses),
    )

    source = "那我們聊點輕鬆的？"
    assert _translator("日文").translate(source) == source


def test_japanese_without_kana_is_not_mistaken_for_a_failure(monkeypatch):
    # 全漢字或只有口頭禪／符號的句子沒有假名也算數，不能白白重試。
    calls = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return _Response("了解。")

    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post", fake_post
    )

    assert _translator("日文").translate("了解。") == "了解。"
    assert len(calls) == 1


def test_english_terms_carried_over_from_the_source_are_not_a_failure(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append(json)
        return _Response("YouTube配信！")

    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post", fake_post
    )

    assert _translator("日文").translate("YouTube直播！") == "YouTube配信！"
    assert len(calls) == 1


def test_simplified_chinese_target_is_not_forced_to_traditional(monkeypatch):
    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post",
        lambda *args, **kwargs: _Response("这是简体字幕。"),
    )

    assert _translator("簡體中文").translate("これは字幕です。") == ("这是简体字幕。")


def test_implicit_japanese_speaker_is_not_pluralized(monkeypatch):
    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post",
        lambda *args, **kwargs: _Response("我們將先收集最可靠的原始資料。"),
    )

    assert _translator().translate("まず一次データを収集するでしょう。") == (
        "我會先收集最可靠的原始資料。"
    )


def test_explicit_japanese_we_stays_plural(monkeypatch):
    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post",
        lambda *args, **kwargs: _Response("我們將先收集原始資料。"),
    )

    assert _translator().translate("私たちはまず一次データを収集する。") == (
        "我們將先收集原始資料。"
    )


def test_character_name_is_not_rewritten_as_homophones(monkeypatch):
    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post",
        lambda *args, **kwargs: _Response("我是「詠莉」。"),
    )

    # 名字由角色設定提供；引擎本身不認得任何角色（見 test_translate_protected_names.py）。
    translator = _translator(protected_names={"詠梨": ["詠莉", "泳梨", "詠利"]})

    assert translator.translate("私は「詠梨」です。") == "我是「詠梨」。"
