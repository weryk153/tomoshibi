"""參考音：每個角色一個資料夾、共用的放 shared/，可以從角色頁上傳 mp3／wav。

GPT-SoVITS 的參考音要 3～10 秒；太長的在句子間的停頓處切到 10 秒內，逐字稿由
語音辨識跟著切好的那段產生，兩者一定對得上。
"""

import io
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydub import AudioSegment
from pydub.generators import Sine

from src.open_llm_vtuber import reference_voices


def speech(*seconds, gap=0.5):
    """幾句「話」（正弦波）中間隔著停頓。"""
    clip = AudioSegment.silent(duration=300)
    for i, length in enumerate(seconds):
        if i:
            clip += AudioSegment.silent(duration=int(gap * 1000))
        clip += (
            Sine(220 + 40 * i)
            .to_audio_segment(duration=int(length * 1000))
            .apply_gain(-6)
        )
    return clip + AudioSegment.silent(duration=300)


def mp3_bytes(clip):
    out = io.BytesIO()
    clip.export(out, format="mp3")
    return out.getvalue()


def test_a_clip_inside_the_limits_is_kept_whole_without_the_silence_around_it():
    cut = reference_voices.fit(speech(2.0, 2.5))
    assert 4.4 <= len(cut) / 1000 <= 5.4


def test_a_long_clip_is_cut_at_a_pause_to_at_most_ten_seconds():
    cut = reference_voices.fit(speech(3.0, 3.5, 3.0, 4.0))  # 13.5 秒的話
    seconds = len(cut) / 1000
    assert 3 <= seconds <= 10
    assert seconds >= 6.5  # 前兩句（加中間的停頓）都在，不是只剩一句


def test_a_clip_too_short_or_one_long_sentence_is_refused():
    with pytest.raises(reference_voices.NotUsable, match="3"):
        reference_voices.fit(speech(1.5))
    with pytest.raises(reference_voices.NotUsable, match="10"):
        reference_voices.fit(speech(12.0))


def test_each_character_has_a_folder_and_shared_is_for_everyone(tmp_path):
    root = tmp_path / "references"
    (root / "pekora").mkdir(parents=True)
    (root / "shared").mkdir()
    for path in (
        "pekora/pekora_default_ja.wav",
        "shared/tsukuyomi_2_ja.wav",
        "loose_ja.wav",
    ):
        speech(4.0).export(root / path, format="wav")
    (root / "pekora" / "pekora_default_ja.txt").write_text("こんぺこ", encoding="utf-8")

    voices = {v["label"]: v for v in reference_voices.voices_in_root(str(root))}
    assert voices["pekora_default_ja"]["owner"] == "pekora"
    assert voices["pekora_default_ja"]["prompt_text"] == "こんぺこ"
    assert voices["tsukuyomi_2_ja"]["owner"] == "shared"
    assert voices["loose_ja"]["owner"] == ""


def test_an_owner_is_a_folder_name_never_a_path():
    for bad in ("../x", "a/b", "", ".", "..", "x\\y"):
        assert reference_voices.owner_folder(bad) is None
    assert reference_voices.owner_folder("march_7th") == "march_7th"
    assert reference_voices.owner_folder("char_16560406") == "char_16560406"


class Ears:
    def __init__(self, heard="この領域の環境パラメータは安定しています。"):
        self.heard = heard
        self.lengths = []

    async def async_transcribe_np(self, audio):
        self.lengths.append(len(audio) / 16000)
        return self.heard


def app(tmp_path, monkeypatch, ears):
    root = tmp_path / "references"
    root.mkdir()
    monkeypatch.setattr(reference_voices, "references_root", lambda: str(root))
    monkeypatch.setattr(reference_voices, "_is_local_request", lambda r: True)
    api = FastAPI()
    api.include_router(reference_voices.init_reference_voice_route(lambda: ears))
    return TestClient(api), root


def test_an_uploaded_mp3_lands_in_her_folder_as_a_wav_with_its_transcript(
    tmp_path, monkeypatch
):
    ears = Ears()
    http, root = app(tmp_path, monkeypatch, ears)
    got = http.post(
        "/api/reference-voices?owner=march_7th&name=" + "march voice.mp3",
        content=mp3_bytes(speech(3.0, 3.5, 3.0, 4.0)),
    )
    assert got.status_code == 200, got.text
    voice = got.json()["voice"]
    assert voice["owner"] == "march_7th" and voice["label"] == "march_voice"
    assert voice["prompt_text"] == ears.heard
    wav = root / "march_7th" / "march_voice.wav"
    assert (
        wav.is_file()
        and (root / "march_7th" / "march_voice.txt").read_text("utf-8") == ears.heard
    )
    seconds = len(AudioSegment.from_wav(wav)) / 1000
    assert 3 <= seconds <= 10
    assert abs(ears.lengths[0] - seconds) < 0.1  # 逐字稿聽的就是存下來的那段


def test_an_upload_does_not_overwrite_a_voice_already_there(tmp_path, monkeypatch):
    http, root = app(tmp_path, monkeypatch, Ears())
    url = "/api/reference-voices?owner=pekora&name=hello.wav"
    first = http.post(url, content=mp3_bytes(speech(4.0))).json()["voice"]
    second = http.post(url, content=mp3_bytes(speech(4.0))).json()["voice"]
    assert first["path"] != second["path"]
    assert sorted(os.listdir(root / "pekora")) == [
        "hello.txt",
        "hello.wav",
        "hello_2.txt",
        "hello_2.wav",
    ]


def test_bad_uploads_are_refused(tmp_path, monkeypatch):
    http, root = app(tmp_path, monkeypatch, Ears())
    assert (
        http.post(
            "/api/reference-voices?owner=../x&name=a.wav", content=b"x"
        ).status_code
        == 400
    )
    assert (
        http.post(
            "/api/reference-voices?owner=pekora&name=a.wav", content=b"not audio"
        ).status_code
        == 400
    )
    short = http.post(
        "/api/reference-voices?owner=pekora&name=a.mp3", content=mp3_bytes(speech(1.0))
    )
    assert short.status_code == 400 and "3" in short.json()["error"]
    assert not (root / "pekora").exists() or not os.listdir(root / "pekora")


def test_without_ears_the_transcript_is_left_for_the_user(tmp_path, monkeypatch):
    http, root = app(tmp_path, monkeypatch, None)
    voice = http.post(
        "/api/reference-voices?owner=pekora&name=a.mp3", content=mp3_bytes(speech(4.0))
    ).json()["voice"]
    assert voice["prompt_text"] == ""
    assert not (root / "pekora" / "a.txt").exists()
