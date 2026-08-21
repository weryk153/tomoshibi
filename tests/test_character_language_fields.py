"""角色編輯表單新增的兩個語言欄位在寫入路徑上的行為。

R（reply_language，她用什麼語言寫）與 V（voice_lang，用什麼語言唸）是兩件事：
兩者相同時語音路徑會跳過翻譯，不同時後端每句都要先翻一次再合成，那是延遲的
主要來源之一。它們住在角色檔的不同位置——R 在頂層，V 在
tts_config.gpt_sovits_tts.text_lang——所以很容易在某一條寫入路徑上漏掉一個，
而漏掉的徵狀只是「這個欄位存不進去」，沒有任何錯誤訊息。

這裡釘住三件事：
1. 兩個欄位各自寫進正確的位置，而且不會互相覆蓋
2. 「缺鍵」與「空字串」是不同的意思——前者保留現值，後者才是清除
3. 更新覆寫檔時，沒帶到的語言欄位要退回磁碟上的現值（那條路徑是整份重寫的）
"""

import pytest
import yaml

from src.open_llm_vtuber import character_route
from src.open_llm_vtuber import conf_editor
from src.open_llm_vtuber.character_route import (
    _build_character_config,
    _extract_body_fields,
    _update_base_character_config,
)


def _build(**kwargs) -> dict:
    base = dict(
        conf_name="紅莉栖",
        conf_uid="kurisu",
        persona_prompt="PERSONA",
        live2d_model_name="kurisu_fan",
        voice=None,
        character_name=None,
        avatar=None,
    )
    base.update(kwargs)
    return _build_character_config(**base)


# ---- _build_character_config（建立角色）----


def test_reply_language_goes_to_the_top_level():
    cc = _build(reply_language="Japanese")

    assert cc["reply_language"] == "Japanese"


def test_voice_lang_goes_under_gpt_sovits_not_the_top_level():
    """V 住在 tts_config.gpt_sovits_tts.text_lang，寫錯層 TTS 讀不到。"""
    cc = _build(voice_lang="ja")

    assert cc["tts_config"]["gpt_sovits_tts"]["text_lang"] == "ja"
    assert "voice_lang" not in cc


def test_voice_lang_does_not_wipe_the_edge_tts_voice():
    """兩者都設時要並存——voice_lang 若整包覆寫 tts_config，聲音就沒了。"""
    cc = _build(voice="zh-TW-HsiaoChenNeural", voice_lang="ja")

    assert cc["tts_config"]["edge_tts"]["voice"] == "zh-TW-HsiaoChenNeural"
    assert cc["tts_config"]["gpt_sovits_tts"]["text_lang"] == "ja"


def test_neither_key_is_written_when_unset():
    """沒設就完全不寫，角色沿用全域值；寫個空字串進去會變成「用空字串回答」。"""
    cc = _build()

    assert "reply_language" not in cc
    assert "tts_config" not in cc


def test_the_two_fields_are_independent():
    only_r = _build(reply_language="Japanese")
    only_v = _build(voice_lang="ja")

    assert "tts_config" not in only_r
    assert "reply_language" not in only_v


# ---- _extract_body_fields（POST/PUT 共用的酬載解析）----


def test_a_missing_key_is_none_not_empty_string():
    """缺鍵＝這次不改。若解析成 ""，每次編輯別的欄位都會把語言清掉。"""
    fields = _extract_body_fields({"conf_name": "x"})

    assert fields["reply_language"] is None
    assert fields["voice_lang"] is None


def test_an_explicit_empty_string_survives_as_empty_string():
    """空字串＝清除。跟缺鍵混為一談的話，這個欄位設了就再也拿不掉。"""
    fields = _extract_body_fields({"reply_language": "", "voice_lang": ""})

    assert fields["reply_language"] == ""
    assert fields["voice_lang"] == ""


def test_whitespace_only_is_stripped_to_empty():
    """一串空白不是語言名稱，要當成清除，否則會寫進提示詞裡。"""
    fields = _extract_body_fields({"reply_language": "   ", "voice_lang": " "})

    assert fields["reply_language"] == ""
    assert fields["voice_lang"] == ""


def test_values_are_trimmed_but_kept():
    fields = _extract_body_fields({"reply_language": " Japanese ", "voice_lang": " ja "})

    assert fields["reply_language"] == "Japanese"
    assert fields["voice_lang"] == "ja"


# ---- _update_base_character_config（編輯 conf.yaml 裡的基底角色）----
#
# 這個函式直接讀寫 CONF_PATH，所以每個測試都把它指到 tmp_path 底下的副本。
# 絕對不能讓測試碰到真正的 conf.yaml。

BASE_CONF = """\
system_config:
  # 這行註解要活下來——ruamel round-trip 的重點就在這裡
  player_language: 'Traditional Chinese (Taiwan)'
character_config:
  conf_name: '紅莉栖'
  persona_prompt: 'PERSONA'
  live2d_model_name: 'kurisu_fan'
  reply_language: 'Japanese'
  tts_config:
    gpt_sovits_tts:
      text_lang: 'ja'
"""


@pytest.fixture
def conf(tmp_path, monkeypatch):
    """把 CONF_PATH 指到暫存副本，回傳一個「讀回目前 character_config」的函式。"""
    path = tmp_path / "conf.yaml"
    path.write_text(BASE_CONF, encoding="utf-8")
    # 兩處都要指過去：character_route 讀它自己的 CONF_PATH，寫入走
    # conf_editor（備份與原子寫入在那裡）。
    monkeypatch.setattr(character_route, "CONF_PATH", str(path))
    monkeypatch.setattr(conf_editor, "CONF_PATH", str(path))

    def read() -> dict:
        return yaml.safe_load(path.read_text(encoding="utf-8"))["character_config"]

    read.path = path
    return read


def _update(**kwargs) -> None:
    base = dict(
        conf_name="紅莉栖",
        persona_prompt="PERSONA",
        live2d_model_name="kurisu_fan",
        voice=None,
        character_name=None,
        avatar=None,
    )
    base.update(kwargs)
    _update_base_character_config(**base)


def test_none_leaves_the_existing_language_alone(conf):
    """只改人設時不該動到語言——這是資料靜靜消失的典型路徑。"""
    _update(persona_prompt="NEW")

    cc = conf()
    assert cc["reply_language"] == "Japanese"
    assert cc["tts_config"]["gpt_sovits_tts"]["text_lang"] == "ja"


def test_an_empty_string_clears_the_reply_language(conf):
    _update(reply_language="")

    assert "reply_language" not in conf()


def test_an_empty_string_clears_the_voice_lang(conf):
    """清掉 text_lang 而不是把 gpt_sovits_tts 整塊刪掉——那裡還有別的設定。"""
    _update(voice_lang="")

    cc = conf()
    assert "text_lang" not in cc["tts_config"]["gpt_sovits_tts"]


def test_a_new_value_replaces_the_old_one(conf):
    _update(reply_language="English", voice_lang="en")

    cc = conf()
    assert cc["reply_language"] == "English"
    assert cc["tts_config"]["gpt_sovits_tts"]["text_lang"] == "en"


def test_the_hand_written_comments_survive(conf):
    """conf.yaml 是人手維護的檔案。ruamel round-trip 壞掉時註解會整批消失。"""
    _update(reply_language="English")

    assert "ruamel round-trip" in conf.path.read_text(encoding="utf-8")
