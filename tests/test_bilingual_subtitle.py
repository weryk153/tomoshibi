"""雙語字幕：開關打開時，畫面字幕多一行她實際唸出來的那句。

佩克拉回覆中文、用日文發聲、字幕看中文：開了以後上行是日文（念的）、下行是中文
（字幕）。關著時 payload 跟以前一模一樣，不多帶欄位。對話紀錄與記憶只看
display_text.text，這裡完全不碰。
"""

import asyncio
import json
from types import SimpleNamespace

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import character_route, character_settings, conf_editor
from src.open_llm_vtuber.agent.output_types import Actions, DisplayText
from src.open_llm_vtuber.config_manager.character import CharacterConfig
from src.open_llm_vtuber.conversations import tts_manager as tts_manager_module
from src.open_llm_vtuber.conversations.bilingual import spoken_line
from src.open_llm_vtuber.conversations.conversation_utils import (
    handle_sentence_output,
    process_agent_output,
)
from src.open_llm_vtuber.conversations.tts_manager import TTSTaskManager
from src.open_llm_vtuber.tts.tts_interface import TTSInterface
from src.open_llm_vtuber.utils.stream_audio import prepare_audio_payload

# ---------------------------------------------------------------- 判斷規則


def test_spoken_line_only_when_enabled():
    assert (
        spoken_line(
            False,
            original_tts="你好！",
            tts_text="こんにちは！",
            display="你好！",
            subtitle="你好！",
        )
        is None
    )


def test_spoken_line_when_the_voice_was_translated():
    assert (
        spoken_line(
            True,
            original_tts="你好！",
            tts_text="こんにちは！",
            display="你好！",
            subtitle="你好！",
        )
        == "こんにちは！"
    )


def test_spoken_line_when_only_the_subtitle_was_translated():
    assert (
        spoken_line(
            True,
            original_tts="こんにちは！",
            tts_text="こんにちは！",
            display="こんにちは！",
            subtitle="你好！",
        )
        == "こんにちは！"
    )


def test_no_spoken_line_when_nothing_was_translated():
    """念的是過濾過的那句（星號動作拿掉了），跟顯示的不完全一樣，但同一個語言，
    不該多出一行幾乎一樣的字。"""
    assert (
        spoken_line(
            True,
            original_tts="你好",
            tts_text="你好",
            display="你好 *笑*",
            subtitle="你好 *笑*",
        )
        is None
    )


def test_no_spoken_line_when_both_lines_read_the_same():
    assert (
        spoken_line(
            True,
            original_tts="hello",
            tts_text=" 你好 ",
            display="hello",
            subtitle="你好",
        )
        is None
    )


# ---------------------------------------------------------------- payload


def _old_silent_payload(display_text, subtitle_text, forwarded=False):
    """改動前 prepare_audio_payload 的靜音 payload，欄位與順序原樣。"""
    return {
        "type": "audio",
        "audio": None,
        "volumes": [],
        "slice_length": 20,
        "display_text": display_text,
        "subtitle_text": subtitle_text,
        "actions": None,
        "forwarded": forwarded,
    }


def test_payload_without_spoken_text_is_byte_identical():
    display = DisplayText(text="你好！", name="佩克拉")
    payload = prepare_audio_payload(
        audio_path=None, display_text=display, subtitle_text="你好！"
    )
    assert json.dumps(payload) == json.dumps(
        _old_silent_payload(display.to_dict(), "你好！")
    )
    assert "spoken_text" not in payload


def test_payload_carries_spoken_text_when_given():
    payload = prepare_audio_payload(
        audio_path=None,
        display_text=DisplayText(text="你好！"),
        subtitle_text="你好！",
        spoken_text="こんにちは！",
    )
    assert payload["spoken_text"] == "こんにちは！"


def test_payload_with_audio_carries_spoken_text(tmp_path):
    from pydub.generators import Sine

    wav = tmp_path / "a.wav"
    Sine(440).to_audio_segment(duration=100).export(wav, format="wav")
    off = prepare_audio_payload(
        audio_path=str(wav), display_text=DisplayText(text="你好！")
    )
    on = prepare_audio_payload(
        audio_path=str(wav),
        display_text=DisplayText(text="你好！"),
        spoken_text="こんにちは！",
    )
    assert list(off) == [
        "type",
        "audio",
        "volumes",
        "slice_length",
        "display_text",
        "subtitle_text",
        "actions",
        "forwarded",
    ]
    assert on["spoken_text"] == "こんにちは！"


def test_forwarded_payload_has_no_spoken_text():
    """群組轉送（audio-play-start 的回音）只帶 display_text。"""
    payload = prepare_audio_payload(
        audio_path=None,
        display_text={"text": "你好！", "name": "佩克拉", "avatar": ""},
        actions=None,
        forwarded=True,
    )
    assert "spoken_text" not in payload


# ---------------------------------------------------------------- 合成管線


class _OkEngine(TTSInterface):
    def generate_audio(self, text, file_name_no_ext=None):  # pragma: no cover
        raise NotImplementedError

    async def async_generate_audio(self, text, file_name_no_ext=None):
        return f"{text}.wav"

    def remove_file(self, filepath, verbose=True):
        pass


def _fake_prepare_audio_payload(audio_path, **kwargs):
    kwargs["audio_path"] = None  # 走真的函式的靜音分支，不用解碼音檔
    payload = prepare_audio_payload(**kwargs)
    payload["audio"] = f"AUDIO:{audio_path}" if audio_path else None
    return payload


class _RecordingSend:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, data: str) -> None:
        self.messages.append(json.loads(data))


class _Sentences:
    def __init__(self, pairs):
        self._pairs = pairs

    async def __aiter__(self):
        for display, tts in self._pairs:
            yield DisplayText(text=display), tts, Actions()


class _Translator:
    def __init__(self, target_lang, table):
        self.target_lang = target_lang
        self.table = table

    def translate(self, text):
        return self.table.get(text, text)


PEKO = {"konpeko": "こんぺこ"}


def _pipeline(monkeypatch, pairs, *, bilingual, audio=None, subtitle=None):
    monkeypatch.setattr(
        tts_manager_module, "prepare_audio_payload", _fake_prepare_audio_payload
    )

    async def _run():
        manager = TTSTaskManager()
        send = _RecordingSend()
        await handle_sentence_output(
            _Sentences(pairs),
            live2d_model=None,
            tts_engine=_OkEngine(),
            websocket_send=send,
            tts_manager=manager,
            translate_engine=audio,
            subtitle_translate_engine=subtitle,
            voice_lang="ja",
            catchphrases=PEKO,
            bilingual_subtitle=bilingual,
        )
        await asyncio.gather(*manager.task_list)
        await manager._payload_queue.join()
        return send.messages

    return asyncio.run(_run())


AUDIO_JA = _Translator("ja", {"今天好嗎？": "今日は元気？"})


def test_off_sends_no_spoken_text(monkeypatch):
    (msg,) = _pipeline(
        monkeypatch, [("今天好嗎？", "今天好嗎？")], bilingual=False, audio=AUDIO_JA
    )
    assert "spoken_text" not in msg
    assert msg["display_text"]["text"] == "今天好嗎？"


def test_on_sends_the_line_she_speaks(monkeypatch):
    (msg,) = _pipeline(
        monkeypatch, [("今天好嗎？", "今天好嗎？")], bilingual=True, audio=AUDIO_JA
    )
    assert msg["spoken_text"] == "今日は元気？"
    assert msg["subtitle_text"] == "今天好嗎？"
    # 紀錄與記憶用的正典文字不變。
    assert msg["display_text"]["text"] == "今天好嗎？"


def test_on_catchphrase_only_sentence(monkeypatch):
    (msg,) = _pipeline(
        monkeypatch, [("konpeko！", "konpeko！")], bilingual=True, audio=AUDIO_JA
    )
    assert msg["spoken_text"] == "こんぺこ！"
    assert msg["subtitle_text"] == "konpeko！"


def test_on_without_any_translation_sends_nothing_extra(monkeypatch):
    """字幕翻譯關、語音也不用翻（同語言）：念的就是顯示的。"""
    (msg,) = _pipeline(
        monkeypatch,
        [("こんにちは *笑う*", "こんにちは")],
        bilingual=True,
        audio=_Translator("ja", {}),
    )
    assert "spoken_text" not in msg


def test_on_with_subtitle_translation_only(monkeypatch):
    (msg,) = _pipeline(
        monkeypatch,
        [("こんにちは", "こんにちは")],
        bilingual=True,
        audio=_Translator("ja", {}),
        subtitle=_Translator("zh", {"こんにちは": "你好"}),
    )
    assert msg["spoken_text"] == "こんにちは"
    assert msg["subtitle_text"] == "你好"


def test_process_agent_output_reads_the_character_switch(monkeypatch):
    seen = {}

    async def _fake_handle(*args, **kwargs):
        seen.update(kwargs)
        return ""

    from src.open_llm_vtuber.conversations import conversation_utils

    monkeypatch.setattr(conversation_utils, "handle_sentence_output", _fake_handle)

    class _Output:
        display_text = DisplayText(text="")

    monkeypatch.setattr(conversation_utils, "SentenceOutput", _Output)
    for flag in (True, False):
        character = SimpleNamespace(
            character_name="佩克拉",
            conf_name="佩克拉",
            avatar="",
            catchphrases={},
            bilingual_subtitle=flag,
        )
        asyncio.run(
            process_agent_output(
                _Output(),
                character_config=character,
                live2d_model=None,
                tts_engine=None,
                websocket_send=None,
                tts_manager=None,
            )
        )
        assert seen["bilingual_subtitle"] is flag


# ---------------------------------------------------------------- 角色設定


def test_character_config_field_defaults_off():
    assert CharacterConfig.model_fields["bilingual_subtitle"].default is False
    assert CharacterConfig.model_fields["bilingual_subtitle"].alias == (
        "bilingual_subtitle"
    )


def test_the_character_owns_the_switch():
    assert character_settings.OWNED["bilingual_subtitle"] == ("bilingual_subtitle",)
    assert "bilingual_subtitle" in character_settings.TOGGLES
    assert character_settings.DEFAULTS["bilingual_subtitle"] is False


BASE = """\
system_config:
  player_language: 'zh-TW'
character_config:
  conf_name: '底稿'
  conf_uid: 'base_uid'
  persona_prompt: |
    你是底稿。

  # 直播平台集成
live_config:
  enabled: False
"""

PEKORA = """\
character_config:
  conf_name: '佩克拉'
  conf_uid: 'pekora'
  # 手寫的註解
  persona_prompt: |
    你是佩克拉。
  live2d_model_name: mao_pro
"""


def _client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(BASE, encoding="utf-8")
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "pekora.yaml").write_text(PEKORA, encoding="utf-8")
    monkeypatch.setattr(conf_editor, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_route, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_settings, "CONF_PATH", "conf.yaml")
    monkeypatch.setattr(character_route, "_is_local_request", lambda r: True)
    monkeypatch.setattr(character_route, "_rescan_skins", lambda: None)
    monkeypatch.setattr(
        character_route, "_load_model_dict", lambda: [{"name": "mao_pro"}]
    )
    app = FastAPI()
    app.include_router(character_route.init_character_route())
    return TestClient(app)


def test_settings_endpoint_reads_and_writes_the_switch(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    url = "/api/characters/pekora.yaml/settings"
    assert http.get(url).json()["settings"]["bilingual_subtitle"] is False
    saved = http.post(url, json={"bilingual_subtitle": True}).json()
    assert saved["ok"] is True
    assert saved["settings"]["bilingual_subtitle"] is True
    text = (tmp_path / "characters" / "pekora.yaml").read_text("utf-8")
    assert "# 手寫的註解" in text
    assert yaml.safe_load(text)["character_config"]["bilingual_subtitle"] is True
    assert http.post(url, json={"bilingual_subtitle": "yes"}).status_code == 400


def test_base_character_switch_goes_to_its_own_line(tmp_path, monkeypatch):
    _client(tmp_path, monkeypatch)
    character_settings.write("conf.yaml", {"bilingual_subtitle": True})
    after = (tmp_path / "conf.yaml").read_text("utf-8").splitlines()
    assert "  bilingual_subtitle: True" in after
    assert after.index("  # 直播平台集成") == after.index("live_config:") - 1
    assert character_settings.effective("conf.yaml")["bilingual_subtitle"] is True


def test_character_list_and_edit_keep_the_switch(tmp_path, monkeypatch):
    http = _client(tmp_path, monkeypatch)
    http.post("/api/characters/pekora.yaml/settings", json={"bilingual_subtitle": True})
    listed = http.get("/api/characters").json()
    records = listed["characters"] if isinstance(listed, dict) else listed
    pekora = next(c for c in records if c["filename"] == "pekora.yaml")
    assert pekora["bilingual_subtitle"] is True

    response = http.put(
        "/api/characters/pekora.yaml",
        json={
            "conf_name": "佩克拉",
            "persona_prompt": "你是兔田佩克拉。\n",
            "live2d_model_name": "mao_pro",
        },
    )
    assert response.status_code == 200, response.text
    saved = yaml.safe_load(
        (tmp_path / "characters" / "pekora.yaml").read_text("utf-8")
    )["character_config"]
    assert saved["bilingual_subtitle"] is True
