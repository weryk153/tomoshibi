"""角色講的語言跟玩家不同時，SenseVoice 辨識語言改用 'auto'。

Bug: pekora.yaml 的聲音語言是日文（gpt_sovits_tts text_lang='ja'），玩家語言是
中文（zh-TW）。之前 ASR 永遠鎖玩家語言 -> 'zh'，導致短句被聽成中文諧音
（「おやすみなさい」被聽成「歐亞蘇明納賽」）。SenseVoice 用 'auto' 時日文可以
正確辨識。

規則：角色聲音語言 V（conversation_utils.derive_voice_lang）有設定，且跟玩家語言
推導出來的不一樣時，改用 'auto'；否則維持原本 clamp 行為不變。

'yue'（廣東話）桶要特別處理：derive_voice_lang 沒有獨立的 yue bucket，廣東話聲音
一律算進 'zh'；但玩家語言 zh-HK / yue-* 會被 clamp 成 'yue'。比較時要把 'yue' 併回
'zh' 的桶，不然廣東話玩家對廣東話角色會被誤判成語言不同而跳成 auto。
"""

import pytest

from types import SimpleNamespace

from src.open_llm_vtuber.service_context import ServiceContext


def _sherpa_asr_config(language="auto", model_type="sense_voice"):
    return SimpleNamespace(
        asr_model="sherpa_onnx_asr",
        sherpa_onnx_asr=SimpleNamespace(
            model_type=model_type,
            language=language,
            model_dump=lambda: {"model_type": model_type, "language": language},
        ),
    )


def _character_config(text_lang):
    """text_lang=None 代表讀不出聲音語言（tts_config 整個沒有）。"""
    if text_lang is None:
        return SimpleNamespace(tts_config=None)
    return SimpleNamespace(
        tts_config=SimpleNamespace(
            tts_model="gpt_sovits_tts",
            gpt_sovits_tts=SimpleNamespace(text_lang=text_lang),
        )
    )


def _context(player_language):
    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(player_language=player_language)
    context.character_config = SimpleNamespace(asr_config=None)
    context.asr_engine = object()  # truthy：跳過真正建立 engine 那段
    return context


def test_japanese_voice_character_with_chinese_player_goes_auto():
    """(a) 角色聲音是日文、玩家語言是中文 -> 'auto'。"""
    context = _context("zh-TW")
    asr_config = _sherpa_asr_config()
    # 讓 identity 相等，跳過真正的 ASRFactory 重建邏輯——這裡只驗證語言推導。
    context.character_config.asr_config = asr_config

    context.init_asr(asr_config, _character_config("all_ja"))

    assert asr_config.sherpa_onnx_asr.language == "auto"


def test_chinese_voice_character_with_chinese_player_unchanged():
    """(b) 角色聲音是中文、玩家語言是中文 -> 維持 'zh'（不變）。"""
    context = _context("zh-TW")
    asr_config = _sherpa_asr_config()
    context.character_config.asr_config = asr_config

    context.init_asr(asr_config, _character_config("all_zh"))

    assert asr_config.sherpa_onnx_asr.language == "zh"


def test_no_voice_language_keeps_old_clamp_behaviour():
    """(c) 讀不出聲音語言（None）-> 維持原本只看玩家語言的 clamp 行為。"""
    context = _context("zh-TW")
    asr_config = _sherpa_asr_config()
    context.character_config.asr_config = asr_config

    context.init_asr(asr_config, _character_config(None))

    assert asr_config.sherpa_onnx_asr.language == "zh"


@pytest.mark.parametrize("text_lang", ["yue", "all_zh"])
def test_cantonese_player_with_cantonese_or_mandarin_voice_stays_yue(text_lang):
    """(e) 玩家語言是廣東話（zh-HK -> clamp 'yue'），角色聲音是廣東話或國語
    （都算進 'zh' bucket）-> 維持 'yue'，不要被誤判成語言不同而跳成 'auto'。"""
    context = _context("zh-HK")
    asr_config = _sherpa_asr_config()
    context.character_config.asr_config = asr_config

    context.init_asr(asr_config, _character_config(text_lang))

    assert asr_config.sherpa_onnx_asr.language == "yue"


def test_switching_back_to_chinese_voice_character_resets_to_zh(monkeypatch):
    """(d) 從日文聲音角色切回中文聲音角色，語言要跟著切回 'zh'，且 ASR engine 真的
    被重建（不是沿用舊的、語言沒跟著換的 engine）。"""
    build_calls = []

    def fake_get_asr_system(requested, **kwargs):
        build_calls.append((requested, kwargs))
        return SimpleNamespace(engine_id=len(build_calls))

    monkeypatch.setattr(
        "src.open_llm_vtuber.service_context.ASRFactory.get_asr_system",
        fake_get_asr_system,
    )

    context = ServiceContext.__new__(ServiceContext)
    context.system_config = SimpleNamespace(player_language="zh-TW")
    context.character_config = SimpleNamespace(asr_config=None)
    context.asr_engine = None

    asr_config_ja = _sherpa_asr_config()
    context.init_asr(asr_config_ja, _character_config("all_ja"))
    assert asr_config_ja.sherpa_onnx_asr.language == "auto"
    assert len(build_calls) == 1

    asr_config_zh = _sherpa_asr_config()
    context.init_asr(asr_config_zh, _character_config("all_zh"))

    assert asr_config_zh.sherpa_onnx_asr.language == "zh"
    # engine 真的被重新建立了一次（language 真的從 'auto' 換回 'zh'，不是沿用舊物件）。
    assert len(build_calls) == 2
