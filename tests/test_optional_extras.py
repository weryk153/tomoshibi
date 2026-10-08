"""選裝套件（例如 faster-whisper）：在設定頁一鍵裝，桌面版之後每次啟動同步時一起帶上。

桌面版每次啟動都跑 `uv sync`，只裝鎖定清單裡的東西；直接 pip 裝進去，下次開 App 就被
清掉。所以裝過的選裝套件記在後端資料夾的 extras.json，安裝與啟動都用
`uv sync --extra <名字>`。
"""

import asyncio
import json
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import optional_extras


async def _nothing_to_prepare():
    return
    yield


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TOMOSHIBI_UV", "/bundled/uv")
    # 測試不真的去下載 1.6GB 的語音模型。
    monkeypatch.setitem(optional_extras.PREPARE, "faster_whisper", _nothing_to_prepare)
    return tmp_path


def test_only_known_extras_are_remembered(workspace):
    assert optional_extras.remembered() == []
    optional_extras.remember("faster_whisper")
    optional_extras.remember("faster_whisper")
    (workspace / "extras.json").write_text(json.dumps(["faster_whisper", "rm -rf"]))
    assert optional_extras.remembered() == ["faster_whisper"]


def test_a_broken_extras_file_is_no_extras(workspace):
    (workspace / "extras.json").write_text("{not json")
    assert optional_extras.remembered() == []


def test_the_sync_command_keeps_what_is_there_and_adds_every_remembered_extra(
    workspace,
):
    optional_extras.remember("faster_whisper")
    command = optional_extras.sync_command(["faster_whisper"])
    assert command[:2] == ["/bundled/uv", "sync"]
    assert "--frozen" in command and "--inexact" in command and "--no-dev" in command
    assert (
        command.count("--extra") == 1
        and command[command.index("--extra") + 1] == "faster_whisper"
    )


def test_without_uv_there_is_no_command(workspace, monkeypatch):
    monkeypatch.delenv("TOMOSHIBI_UV")
    monkeypatch.setattr(optional_extras.shutil, "which", lambda name: None)
    assert optional_extras.sync_command(["faster_whisper"]) is None


def run_install(extra):
    async def collect():
        return [event async for event in optional_extras.install(extra)]

    return asyncio.run(collect())


def test_a_successful_install_is_remembered_and_reported(workspace, monkeypatch):
    script = "print('Resolved 1 package'); print('Installed faster-whisper')"
    monkeypatch.setattr(
        optional_extras, "sync_command", lambda extras: [sys.executable, "-c", script]
    )
    monkeypatch.setattr(optional_extras, "available", lambda extra: True)
    events = run_install("faster_whisper")
    assert [e["status"] for e in events][-1] == "success"
    assert any(e.get("line") == "Installed faster-whisper" for e in events)
    assert optional_extras.remembered() == ["faster_whisper"]


def test_a_failed_install_is_an_error_and_not_remembered(workspace, monkeypatch):
    script = "import sys; print('network down'); sys.exit(2)"
    monkeypatch.setattr(
        optional_extras, "sync_command", lambda extras: [sys.executable, "-c", script]
    )
    events = run_install("faster_whisper")
    assert events[-1]["status"] == "error" and "network down" in events[-1]["error"]
    assert optional_extras.remembered() == []


def test_an_unknown_extra_is_refused():
    events = run_install("rm -rf")
    assert events == [{"status": "error", "error": "Unknown package: rm -rf"}]


def test_the_status_and_install_endpoints(workspace, monkeypatch):
    monkeypatch.setattr(optional_extras, "_is_local_request", lambda request: True)
    monkeypatch.setattr(optional_extras, "available", lambda extra: False)
    app = FastAPI()
    app.include_router(optional_extras.init_extras_route())
    http = TestClient(app)
    status = http.get("/api/extras/faster_whisper").json()
    assert status == {
        "name": "faster_whisper",
        "available": False,
        "installing": False,
        "download_mb": optional_extras.EXTRAS["faster_whisper"]["download_mb"],
    }
    assert http.get("/api/extras/nope").status_code == 404
    monkeypatch.setattr(
        optional_extras,
        "sync_command",
        lambda extras: [sys.executable, "-c", "print('ok')"],
    )
    monkeypatch.setattr(optional_extras, "available", lambda extra: True)
    lines = [
        json.loads(line)
        for line in http.post("/api/extras/faster_whisper/install").text.splitlines()
    ]
    assert lines[-1]["status"] == "success"


def test_installing_also_downloads_what_the_package_needs_with_progress(
    workspace, monkeypatch
):
    """faster-whisper 的語音模型（約 1.6GB）也在安裝這一步下載，畫面看得到進度；
    以前是重新載入時在後端默默下載，畫面一直「載入中」。"""
    monkeypatch.setattr(
        optional_extras,
        "sync_command",
        lambda extras: [sys.executable, "-c", "print('ok')"],
    )
    monkeypatch.setattr(optional_extras, "available", lambda extra: True)

    async def prepare():
        for done in (0, 800, 1600):
            yield {"status": "model", "completed": done, "total": 1600}

    monkeypatch.setitem(optional_extras.PREPARE, "faster_whisper", prepare)
    events = run_install("faster_whisper")
    progress = [e["completed"] for e in events if e["status"] == "model"]
    assert progress == [0, 800, 1600] and events[-1]["status"] == "success"


def test_a_model_download_that_fails_is_an_error_but_the_package_stays(
    workspace, monkeypatch
):
    monkeypatch.setattr(
        optional_extras,
        "sync_command",
        lambda extras: [sys.executable, "-c", "print('ok')"],
    )
    monkeypatch.setattr(optional_extras, "available", lambda extra: True)

    async def prepare():
        yield {"status": "model", "completed": 0, "total": 1600}
        raise OSError("connection reset")

    monkeypatch.setitem(optional_extras.PREPARE, "faster_whisper", prepare)
    events = run_install("faster_whisper")
    assert events[-1]["status"] == "error" and "connection reset" in events[-1]["error"]
    assert optional_extras.remembered() == ["faster_whisper"]  # 再按一次只要補下載模型


def test_the_whisper_model_comes_from_the_settings(workspace):
    (workspace / "conf.yaml").write_text(
        "character_config:\n  asr_config:\n    faster_whisper:\n"
        "      model_path: 'small'\n      download_root: 'models/whisper'\n",
        encoding="utf-8",
    )
    assert optional_extras.whisper_model_settings() == ("small", "models/whisper")


def test_folder_size_counts_what_is_on_disk(tmp_path):
    tmp_path = tmp_path / "repo"
    tmp_path.mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "blob").write_bytes(b"x" * 300)
    (tmp_path / "b.incomplete").write_bytes(b"x" * 200)
    assert optional_extras.folder_size(str(tmp_path)) == 500
    assert optional_extras.folder_size(str(tmp_path / "missing")) == 0


def test_the_model_step_shows_up_before_its_size_is_known(workspace, monkeypatch):
    """問總大小要好幾秒：在那之前就先回報「開始準備下載模型」，畫面不會停在上一行
    安裝訊息上。"""
    import faster_whisper.utils as whisper_utils

    order = []
    monkeypatch.setattr(
        optional_extras,
        "whisper_model_settings",
        lambda: ("tiny", str(workspace / "models")),
    )
    monkeypatch.setattr(
        optional_extras, "_repo_size", lambda repo: order.append("size") or 1000
    )
    monkeypatch.setattr(
        whisper_utils, "download_model", lambda *a, **k: order.append("download")
    )

    async def collect():
        events = []
        async for event in optional_extras._download_whisper_model():
            events.append(event)
            order.append("event")
        return events

    events = asyncio.run(collect())
    assert order[0] == "event" and events[0] == {
        "status": "model",
        "completed": 0,
        "total": 0,
    }
