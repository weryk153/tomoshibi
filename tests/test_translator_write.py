"""翻譯設定的寫入——重寫前的特徵測試。

這個寫入器一個測試都沒有，但它動的是 conf.yaml：寫錯型別會讓 Pydantic 那關擋下、
寫掉某個子區塊會讓驗證失敗、洗掉註解使用者會發現自己寫的說明不見了。

契約：

- translate_audio 是布林，要寫成裸的 True／False（加引號就變字串了）。
- 只改被要求的那幾個葉節點，其餘的一個字都不動——尤其不能刪掉或清空
  llm／deeplx 子區塊，驗證器要求啟用中的供應商區塊必須存在。
- 舊的 conf.yaml 沒有字幕那兩行時要自己補上，不能整個存檔失敗。
- 註解與縮排原樣保留。
"""

import pytest
from ruamel.yaml import YAML

from src.open_llm_vtuber import conf_editor as ce
from src.open_llm_vtuber import translator_route as tr


CONF = """\
system_config:
  port: 12393
character_config:
  tts_config:
    edge_tts:
      voice: 'zh-CN-XiaoxiaoNeural'  # 預設嗓音
  tts_preprocessor_config:
    translator_config:
      translate_audio: False
      translate_provider: 'deeplx'
      deeplx:
        deeplx_target_lang: 'JA'
        deeplx_api_endpoint: 'http://localhost:1188/v2/translate'
      llm:
        target_lang: '日文'
        api_endpoint: 'http://localhost:1234/v1'
        model: 'qwen'
"""


@pytest.fixture()
def conf(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(tr, "CONF_PATH", str(path))
    return path


def _parsed(conf):
    return YAML(typ="safe").load(conf.read_text(encoding="utf-8"))


def _translator(conf):
    return _parsed(conf)["character_config"]["tts_preprocessor_config"][
        "translator_config"
    ]


def _write(**kwargs):
    base = dict(
        enabled=True,
        engine="llm",
        speak_voice=None,
        deeplx_endpoint=None,
        deeplx_target_lang=None,
        llm_target_lang=None,
        llm_api_endpoint=None,
        llm_model=None,
    )
    base.update(kwargs)
    return tr._write_translator_config(**base)


def test_toggle_writes_a_bare_bool(conf):
    _write(enabled=True, engine="llm")

    assert _translator(conf)["translate_audio"] is True


def test_provider_is_written_as_a_quoted_string(conf):
    _write(enabled=True, engine="deeplx")

    assert _translator(conf)["translate_provider"] == "deeplx"


def test_nested_llm_leaves_are_rewritten(conf):
    _write(
        engine="llm",
        llm_target_lang="英文",
        llm_api_endpoint="http://example/v1",
        llm_model="gpt",
    )
    llm = _translator(conf)["llm"]

    assert llm == {
        "target_lang": "英文",
        "api_endpoint": "http://example/v1",
        "model": "gpt",
    }


def test_nested_deeplx_leaves_are_rewritten(conf):
    _write(
        engine="deeplx",
        deeplx_target_lang="KO",
        deeplx_endpoint="http://elsewhere/v2/translate",
    )
    deeplx = _translator(conf)["deeplx"]

    assert deeplx["deeplx_target_lang"] == "KO"
    assert deeplx["deeplx_api_endpoint"] == "http://elsewhere/v2/translate"


def test_the_other_providers_block_is_left_intact(conf):
    # 驗證器要求啟用中供應商的區塊非空；砍掉另一個等於埋一顆待爆的雷。
    _write(engine="llm", llm_model="gpt")
    translator = _translator(conf)

    assert translator["deeplx"]["deeplx_target_lang"] == "JA"


def test_missing_subtitle_leaves_are_inserted_not_fatal(conf):
    # 舊的 conf.yaml 沒有字幕那兩行。整個存檔不該因此失敗。
    _write(engine="llm", subtitle_enabled=True, subtitle_target_lang="繁體中文")
    translator = _translator(conf)

    assert translator["translate_subtitle"] is True
    assert translator["subtitle_target_lang"] == "繁體中文"


def test_edge_tts_voice_can_be_set_from_here(conf):
    _write(engine="llm", speak_voice="ja-JP-NanamiNeural")
    voice = _parsed(conf)["character_config"]["tts_config"]["edge_tts"]["voice"]

    assert voice == "ja-JP-NanamiNeural"


def test_comments_and_untouched_settings_survive(conf):
    _write(engine="llm", llm_model="gpt")
    text = conf.read_text(encoding="utf-8")

    assert "# 預設嗓音" in text
    assert _parsed(conf)["system_config"]["port"] == 12393


def test_report_lists_what_was_written(conf):
    written = _write(engine="llm", llm_model="gpt")

    assert written["translate_provider"] == "llm"
    assert written["llm.model"] == "gpt"


def test_missing_translator_block_raises(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text("system_config:\n  port: 1\n", encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(tr, "CONF_PATH", str(path))

    with pytest.raises(KeyError):
        _write(engine="llm")


# --- 從玩家的 LLM 推導翻譯端點 ------------------------------------------------

ACTIVE_LMSTUDIO = """\
character_config:
  agent_config:
    agent_settings:
      basic_memory_agent:
        llm_provider: 'lmstudio_llm'
    llm_configs:
      openai_compatible_llm:
        base_url: 'http://localhost:11434/v1'
        model: 'qwen2.5:3b'
      lmstudio_llm:
        base_url: 'http://127.0.0.1:1234/v1'
        model: 'qwen/qwen3.5-9b'
  tts_preprocessor_config:
    translator_config:
      translate_audio: False
      translate_provider: 'llm'
      llm:
        target_lang: '日文'
        api_endpoint: ''
        model: ''
"""


def test_llm_defaults_follow_the_active_provider(tmp_path, monkeypatch):
    """實測抓到的 bug：使用者用 LM Studio，存一次翻譯設定就被改成 Ollama 的端點。

    推導寫死讀 openai_compatible_llm，無視 basic_memory_agent.llm_provider 指到
    哪裡。結果是「打開翻譯 → 翻譯連到一個根本沒在跑的服務」，而且它還順手把
    conf.yaml 裡正確的值覆蓋掉了。

    跟記憶整理那條路是同一類錯誤（resolve_consolidation_llm 已經修過）：凡是要
    沿用「玩家設好的 LLM」的地方，都必須跟著當前啟用的供應商走。
    """
    path = tmp_path / "conf.yaml"
    path.write_text(ACTIVE_LMSTUDIO, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(tr, "CONF_PATH", str(path))

    settings = tr._engine_settings_from({}, "llm")

    assert settings["llm_api_endpoint"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert settings["llm_model"] == "qwen/qwen3.5-9b"


def test_explicit_values_are_not_overridden_by_derivation(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(ACTIVE_LMSTUDIO, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(tr, "CONF_PATH", str(path))

    settings = tr._engine_settings_from(
        {"llm_endpoint": "http://mine/v1/chat/completions", "llm_model": "mine"}, "llm"
    )

    assert settings["llm_api_endpoint"] == "http://mine/v1/chat/completions"
    assert settings["llm_model"] == "mine"
