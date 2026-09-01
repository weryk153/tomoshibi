"""翻譯路徑也要吃角色的專有名詞名單，而且不能內建任何角色名字。

字幕是顯示用的，不是對名字做在地化。小模型即使拿到嚴格指令，仍反覆把專有名詞
寫成同音字，所以除了在 prompt 裡交代，還要在輸出端確定性地折回去。
"""

from src.open_llm_vtuber.translate.llm_translate import LLMTranslate


class _Response:
    def __init__(self, content: str):
        self._content = content

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": self._content}}]}


def _translator(protected_names=None) -> LLMTranslate:
    return LLMTranslate(
        api_endpoint="http://translator.test/v1/chat/completions",
        model="local-model",
        target_lang="繁體中文",
        extra_body={"reasoning_effort": "none"},
        timeout=17,
        protected_names=protected_names,
    )


def test_supplied_names_are_restored_in_the_translation(monkeypatch):
    monkeypatch.setattr(
        "src.open_llm_vtuber.translate.llm_translate.httpx.post",
        lambda *args, **kwargs: _Response("我是「愛萊」。"),
    )

    out = _translator({"愛徠": ["愛萊"]}).translate("私は「愛徠」です。")

    assert out == "我是「愛徠」。"


def test_no_character_name_is_hardcoded_in_the_prompt():
    """沒給名單時，system prompt 不可以提到任何具體的角色名字。"""
    prompt = _translator()._system_prompt()

    assert "紅莉栖" not in prompt
    assert "牧瀨" not in prompt


def test_supplied_names_appear_in_the_prompt():
    """給了名單就把正式寫法交代給模型，這是第一道防線。"""
    prompt = _translator({"愛徠": ["愛萊"]})._system_prompt()

    assert "愛徠" in prompt
