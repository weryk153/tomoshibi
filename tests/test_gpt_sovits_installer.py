"""GPT-SoVITS 一鍵安裝：續傳、校驗、依賴替換、參考音挑選、語言沿用、自動啟動條件。

真正的下載、安裝與合成在 CI 的 gpt-sovits-installer-smoke.yml 跑；這裡把網路假造掉。
"""

import asyncio
import hashlib
import io
import json
import re
import shutil
import zipfile
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import gpt_sovits_installer as gi
from src.open_llm_vtuber import gpt_sovits_route as route
from src.open_llm_vtuber import gpt_sovits_service as gs

TEMPLATE = Path("config_templates/conf.tomoshibi.default.yaml").resolve()
BLOB = bytes(range(256)) * 4000


def _item(sha256: str = hashlib.sha256(BLOB).hexdigest()) -> gi.Download:
    return gi.Download(
        "downloads/x.bin", "https://example.test/x.bin", len(BLOB), sha256
    )


def _transport(*, ranges: bool = True, seen: list | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        header = request.headers.get("range")
        if seen is not None:
            seen.append(header)
        if header and ranges:
            start = int(header.removeprefix("bytes=").split("-")[0])
            return httpx.Response(206, content=BLOB[start:])
        return httpx.Response(200, content=BLOB)

    return httpx.MockTransport(handler)


def _fetch(item: gi.Download, root: Path, transport: httpx.MockTransport):
    async def run():
        progress = gi._Progress(item.size)
        async with httpx.AsyncClient(transport=transport) as client:
            events = [e async for e in gi._fetch(client, item, root, progress) if e]
        return events, progress

    return asyncio.run(run())


def _partial(root: Path, size: int) -> Path:
    part = root / "downloads" / "x.bin.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(BLOB[:size])
    return part


def test_interrupted_download_resumes_where_it_stopped(tmp_path):
    part = _partial(tmp_path, 100_000)
    seen: list = []
    events, progress = _fetch(_item(), tmp_path, _transport(seen=seen))
    assert seen == ["bytes=100000-"]
    assert (tmp_path / "downloads" / "x.bin").read_bytes() == BLOB
    assert not part.exists()
    assert events[-1] == {
        "status": "downloading",
        "completed": len(BLOB),
        "total": len(BLOB),
    }


def test_server_without_range_support_starts_over_cleanly(tmp_path):
    _partial(tmp_path, 100_000)
    _, progress = _fetch(_item(), tmp_path, _transport(ranges=False))
    assert (tmp_path / "downloads" / "x.bin").read_bytes() == BLOB
    assert progress.done == len(BLOB)


def test_checksum_mismatch_is_rejected_and_discarded(tmp_path):
    with pytest.raises(gi.InstallError):
        _fetch(_item("0" * 64), tmp_path, _transport())
    assert not (tmp_path / "downloads" / "x.bin").exists()
    assert not (tmp_path / "downloads" / "x.bin.part").exists()


def test_finished_download_is_not_fetched_again(tmp_path):
    dest = tmp_path / "downloads" / "x.bin"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(BLOB)

    def refuse(request):
        raise AssertionError("should not download again")

    events, _ = _fetch(_item(), tmp_path, httpx.MockTransport(refuse))
    assert events == [
        {"status": "downloading", "completed": len(BLOB), "total": len(BLOB)}
    ]


def test_every_download_is_pinned():
    items = gi.MAC_DOWNLOADS + gi.WINDOWS_DOWNLOADS
    for item in items:
        assert re.fullmatch(r"[0-9a-f]{64}", item.sha256), item.path
        assert item.size > 0
        assert "/resolve/main/" not in item.url  # 釘 commit，不追 main
    assert len({item.path for item in items}) == len(items)


def test_mac_requirements_need_no_compiler():
    official = (
        "--no-binary=opencc\nnumpy<2.0\npyopenjtalk>=0.4.1\njieba_fast\njieba\nopencc\n"
        "python_mecab_ko; sys_platform != 'win32'\ntorchaudio\n"
    )
    lines = gi.mac_requirements(official).splitlines()
    assert "--no-binary=opencc" not in lines
    assert "jieba_fast" not in lines
    assert not any(line.startswith("pyopenjtalk>") for line in lines)
    for wanted in (
        "opencc",
        "pyopenjtalk-plus",
        "jieba",
        "torch<2.9",
        "torchaudio<2.9",
    ):
        assert wanted in lines


def test_reference_is_7_to_10_seconds_with_few_katakana():
    per_sec = 96000 * 4
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for key, seconds in (("A_001", 5), ("A_002", 8), ("A_003", 9), ("A_004", 8)):
            z.writestr(f"corpus/01 WAV/{key}.wav", b"\0" * (per_sec * seconds))
        z.writestr(
            "corpus/台本/01 補足なし台本.txt",
            "A_001:みじかいです。\nA_002:テレビとラジオとカメラ。\n"
            "A_003:きょうはいいてんきです。\nA_004:あしたもはれるでしょう。\n",
        )
    with zipfile.ZipFile(buf) as z:
        info, text = gi.pick_reference(z)
    # A_001 太短、A_002 片假名太多；剩下兩句片假名一樣少，取比較長的。
    assert info.filename.endswith("A_003.wav")
    assert text == "きょうはいいてんきです。"


@pytest.mark.parametrize(
    ("tts", "expected"),
    [
        ({"tts_model": "edge_tts", "edge_tts": {"voice": "zh-CN-XiaoyiNeural"}}, "zh"),
        ({"tts_model": "edge_tts", "edge_tts": {"voice": "ja-JP-NanamiNeural"}}, "ja"),
        (
            {"tts_model": "gpt_sovits_tts", "gpt_sovits_tts": {"text_lang": "all_ko"}},
            "ko",
        ),
        ({"tts_model": "edge_tts", "edge_tts": {"voice": "de-DE-KatjaNeural"}}, "ja"),
        ({}, "ja"),
    ],
)
def test_switching_engine_keeps_the_spoken_language(tts, expected):
    assert route.voice_text_lang({"character_config": {"tts_config": tts}}) == expected


def test_installed_voice_is_written_to_conf(tmp_path, monkeypatch):
    shutil.copy(TEMPLATE, tmp_path / "conf.yaml")
    monkeypatch.chdir(tmp_path)
    reference = {
        "path": str(tmp_path / "ref.wav"),
        "prompt_text": "テスト。",
        "prompt_lang": "ja",
    }
    route._use_installed_voice(reference)
    tts = yaml.safe_load((tmp_path / "conf.yaml").read_text(encoding="utf-8"))[
        "character_config"
    ]["tts_config"]
    assert tts["tts_model"] == "gpt_sovits_tts"
    assert tts["gpt_sovits_tts"]["api_url"] == "http://127.0.0.1:9880/tts"
    assert tts["gpt_sovits_tts"]["ref_audio_path"] == reference["path"]
    assert tts["gpt_sovits_tts"]["prompt_text"] == "テスト。"
    assert tts["gpt_sovits_tts"]["prompt_lang"] == "ja"
    # 模板預設是中文的 Edge TTS 聲音，換引擎後照樣講中文。
    assert tts["gpt_sovits_tts"]["text_lang"] == "zh"


def _character(model: str, url: str) -> str:
    return yaml.safe_dump(
        {
            "character_config": {
                "tts_config": {"tts_model": model, "gpt_sovits_tts": {"api_url": url}}
            }
        }
    )


def test_autostart_only_when_a_config_uses_the_local_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(
        _character("edge_tts", "http://127.0.0.1:9880/tts")
    )
    assert gs.wanted_by_config() is False
    (tmp_path / "characters").mkdir()
    (tmp_path / "characters" / "lan.yaml").write_text(
        _character("gpt_sovits_tts", "http://192.168.1.5:9880/tts")
    )
    assert gs.wanted_by_config() is False  # 別台機器上的，不歸我們開
    (tmp_path / "characters" / "me.yaml").write_text(
        _character("gpt_sovits_tts", "http://localhost:9880/tts")
    )
    assert gs.wanted_by_config() is True


def test_marker_counts_only_when_python_exists(tmp_path, monkeypatch):
    monkeypatch.setenv(gi.DIR_ENV, str(tmp_path))
    assert gi.read_marker() is None
    (tmp_path / gi.MARKER).write_text(json.dumps({"python": str(tmp_path / "missing")}))
    assert gi.read_marker() is None
    python = tmp_path / "python"
    python.write_text("")
    (tmp_path / gi.MARKER).write_text(json.dumps({"python": str(python)}))
    assert gi.read_marker()["python"] == str(python)


def test_start_reuses_an_api_that_already_answers(monkeypatch):
    monkeypatch.setattr(gs, "_proc", None)
    monkeypatch.setattr(gs, "api_ready", lambda timeout=2.0: True)

    def refuse(*args, **kwargs):
        raise AssertionError("should not start a second API")

    monkeypatch.setattr(gs.subprocess, "Popen", refuse)
    assert gs.start() is True


def test_status_reports_install_state(tmp_path, monkeypatch):
    monkeypatch.setenv(gi.DIR_ENV, str(tmp_path))
    monkeypatch.setattr(route, "_is_local_request", lambda request: True)
    monkeypatch.setattr(gs, "api_ready", lambda timeout=2.0: False)
    app = FastAPI()
    app.include_router(route.init_gpt_sovits_route())
    with TestClient(app) as client:
        data = client.get("/api/gpt-sovits").json()
    assert data["installed"] is False
    assert data["installing"] is False
    assert data["install_dir"] == str(tmp_path)
    assert data["download_bytes"] > 0


def test_mac_packages_are_pinned_to_a_known_good_set():
    lines = [
        line
        for line in gi.MAC_CONSTRAINTS.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert all(re.fullmatch(r"[A-Za-z0-9_.\-]+==\S+", line) for line in lines)
    pins = {
        name.lower().replace("_", "-"): version
        for name, version in (line.split("==", 1) for line in lines)
    }
    # 沒釘的時候解析器挑過 gradio 3 配 gradio_client 2，API 一啟動就壞。
    assert pins["gradio"].startswith("4.")
    assert pins["gradio-client"].startswith("1.")
    # torchaudio 2.9 起讀參考音要 TorchCodec。
    assert int(pins["torch"].split(".")[1]) < 9
    assert "pyopenjtalk-plus" in pins and "jieba-fast" not in pins
