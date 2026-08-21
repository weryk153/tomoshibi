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


def _translator(target: str = "繁體中文") -> LLMTranslate:
    return LLMTranslate(
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


def test_kurisu_name_is_not_rewritten_as_homophones(monkeypatch):
    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post",
        lambda *args, **kwargs: _Response("我是「紅麗棲」。"),
    )

    assert _translator().translate("私は「紅莉栖」です。") == "我是「紅莉栖」。"
