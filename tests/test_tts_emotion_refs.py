"""依情緒切換參考音：語氣動態控制的行為契約。

參考音決定 GPT-SoVITS 的語氣。在這之前整支只有一個寫死的 ref_audio_path，所以
不管她臉上是什麼表情，聲音永遠同一個語氣——臉在笑，聲音是平的。

這裡釘四件事：
- 對得上就換參考音，而且逐字稿要跟著換（給錯的 prompt_text 輸出會歪掉）。
- 對不上、檔案不在、沒設定，一律退回預設。語氣不對總比沒聲音好。
- 半套的設定項不收——寧可退回預設，也不要拿錯的逐字稿去對齊。
- 沒宣告支援的引擎完全看不到 emotion 這個參數。
"""

import pytest

from src.open_llm_vtuber.tts.gpt_sovits_tts import TTSEngine


@pytest.fixture
def ref_files(tmp_path):
    happy = tmp_path / "happy.wav"
    happy.write_bytes(b"RIFF")
    default = tmp_path / "default.wav"
    default.write_bytes(b"RIFF")
    return {"happy": str(happy), "default": str(default)}


def _engine(ref_files, emotion_refs):
    return TTSEngine(
        ref_audio_path=ref_files["default"],
        prompt_text="預設的逐字稿",
        prompt_lang="ja",
        emotion_refs=emotion_refs,
    )


def test_matching_emotion_swaps_audio_and_its_transcript(ref_files):
    """參考音跟逐字稿是一組的，不能只換一半。"""
    e = _engine(
        ref_files,
        {
            "happy": {
                "ref_audio_path": ref_files["happy"],
                "prompt_text": "開心的逐字稿",
            }
        },
    )
    assert e._ref_for("happy") == (ref_files["happy"], "開心的逐字稿", "ja")


def test_emotion_lookup_is_case_insensitive(ref_files):
    """LLM 寫的是 [Happy] 還是 [happy] 不該有差。"""
    e = _engine(
        ref_files,
        {"Happy": {"ref_audio_path": ref_files["happy"], "prompt_text": "開心"}},
    )
    assert e._ref_for("HAPPY")[0] == ref_files["happy"]


def test_per_emotion_prompt_lang_overrides_the_default(ref_files):
    e = _engine(
        ref_files,
        {
            "happy": {
                "ref_audio_path": ref_files["happy"],
                "prompt_text": "開心",
                "prompt_lang": "zh",
            }
        },
    )
    assert e._ref_for("happy")[2] == "zh"


def test_unknown_emotion_falls_back(ref_files):
    e = _engine(
        ref_files,
        {"happy": {"ref_audio_path": ref_files["happy"], "prompt_text": "開心"}},
    )
    assert e._ref_for("angry") == (ref_files["default"], "預設的逐字稿", "ja")


def test_no_emotion_falls_back(ref_files):
    e = _engine(
        ref_files,
        {"happy": {"ref_audio_path": ref_files["happy"], "prompt_text": "開心"}},
    )
    assert e._ref_for(None)[0] == ref_files["default"]


def test_no_config_means_current_behaviour(ref_files):
    """沒設 emotion_refs 就是原本的樣子：整段對話一個語氣。"""
    e = _engine(ref_files, None)
    assert e._ref_for("happy")[0] == ref_files["default"]


def test_missing_file_falls_back(ref_files):
    """設定寫了但檔案沒錄——退回預設，不要讓 TTS 收到不存在的路徑。"""
    e = _engine(
        ref_files,
        {"happy": {"ref_audio_path": "/nowhere/nope.wav", "prompt_text": "開心"}},
    )
    assert e._ref_for("happy")[0] == ref_files["default"]


def test_half_configured_entries_are_dropped(ref_files):
    """少了逐字稿的項目不收：拿錯的 prompt_text 對齊比退回預設更糟。"""
    e = _engine(
        ref_files,
        {
            "happy": {"ref_audio_path": ref_files["happy"]},  # 缺 prompt_text
            "sad": {"prompt_text": "難過"},  # 缺 ref_audio_path
        },
    )
    assert e.emotion_refs == {}
    assert e._ref_for("happy")[0] == ref_files["default"]


def test_garbage_config_does_not_crash(ref_files):
    assert _engine(ref_files, "不是 dict").emotion_refs == {}
    assert _engine(ref_files, {"happy": "也不是 dict"}).emotion_refs == {}


def test_engine_declares_emotion_support():
    """TTSManager 靠這個旗標決定要不要傳 emotion；預設引擎一律不支援。"""
    from src.open_llm_vtuber.tts.tts_interface import TTSInterface

    assert TTSEngine.supports_emotion is True
    assert TTSInterface.supports_emotion is False
