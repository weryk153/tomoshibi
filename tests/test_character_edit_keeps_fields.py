"""在角色頁編輯一個角色，表單沒有的欄位不能被刪掉。

以前更新角色檔是用表單那幾欄整份重寫：紅莉栖的 protected_names、表情測試角色
自己關掉的長期記憶與字幕翻譯、gpt_sovits 的 api_url……存一次就全沒了，畫面上
沒有任何警告。
"""

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import character_route


def _edit(tmp_path, monkeypatch, original, change):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(character_route, "_rescan_skins", lambda: None)
    monkeypatch.setattr(
        character_route, "_load_model_dict", lambda: [{"name": "mao_pro"}]
    )
    monkeypatch.setattr(
        character_route, "_is_local_request", lambda request: True, raising=False
    )
    path = tmp_path / "characters" / "kurisu.yaml"
    path.parent.mkdir()
    path.write_text(
        yaml.safe_dump({"character_config": original}, allow_unicode=True),
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(character_route.init_character_route())
    body = {
        "conf_name": original["conf_name"],
        "persona_prompt": original["persona_prompt"],
        "live2d_model_name": original["live2d_model_name"],
        **change,
    }
    with TestClient(app) as client:
        response = client.put("/api/characters/kurisu.yaml", json=body)
    assert response.status_code == 200, response.text
    return yaml.safe_load(path.read_text(encoding="utf-8"))["character_config"]


ORIGINAL = {
    "conf_uid": "kurisu",
    "conf_name": "紅莉栖",
    "character_name": "紅莉栖",
    "persona_prompt": "你是紅莉栖。\n",
    "live2d_model_name": "mao_pro",
    "protected_names": {"岡部倫太郎": ["岡部", "鳳凰院"]},
    "long_term_memory_enabled": False,
    "tts_preprocessor_config": {"translator_config": {"translate_subtitle": False}},
    "tts_config": {
        "tts_model": "gpt_sovits_tts",
        "gpt_sovits_tts": {
            "api_url": "http://127.0.0.1:9880/tts",
            "text_lang": "ja",
            "ref_audio_path": "ref/kurisu.wav",
            "prompt_text": "こんにちは",
            "prompt_lang": "ja",
        },
    },
}


def test_fields_the_form_does_not_have_are_kept(tmp_path, monkeypatch):
    saved = _edit(
        tmp_path, monkeypatch, ORIGINAL, {"persona_prompt": "你是牧瀨紅莉栖。\n"}
    )

    assert saved["persona_prompt"].strip() == "你是牧瀨紅莉栖。"
    assert saved["protected_names"] == ORIGINAL["protected_names"]
    assert saved["long_term_memory_enabled"] is False
    assert saved["tts_preprocessor_config"] == ORIGINAL["tts_preprocessor_config"]
    assert (
        saved["tts_config"]["gpt_sovits_tts"]["api_url"] == "http://127.0.0.1:9880/tts"
    )
    assert saved["tts_config"]["gpt_sovits_tts"]["ref_audio_path"] == "ref/kurisu.wav"
    assert saved["tts_config"]["tts_model"] == "gpt_sovits_tts"


def test_what_the_form_owns_still_follows_the_form(tmp_path, monkeypatch):
    saved = _edit(
        tmp_path,
        monkeypatch,
        ORIGINAL,
        {"voice_lang": "", "tts_model": "edge_tts", "voice": "ja-JP-NanamiNeural"},
    )

    assert "text_lang" not in saved["tts_config"]["gpt_sovits_tts"]
    assert saved["tts_config"]["tts_model"] == "edge_tts"
    assert saved["tts_config"]["edge_tts"]["voice"] == "ja-JP-NanamiNeural"
    # 表單沒管的鄰居還在。
    assert (
        saved["tts_config"]["gpt_sovits_tts"]["api_url"] == "http://127.0.0.1:9880/tts"
    )
