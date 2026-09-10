"""一鍵安裝 Ollama。

網路一律用 httpx.MockTransport 假造；macOS 的解壓與複製用真的 ditto 跑一次，
因為那正是會出錯的地方（zipfile 會弄壞 .app 的簽章，才改用 ditto）。
"""

import asyncio
import hashlib
import subprocess
import sys

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import llm_config_route as route
from src.open_llm_vtuber import ollama_installer as oi


def test_tag_from_location():
    loc = "https://github.com/ollama/ollama/releases/download/v0.34.0/Ollama-darwin.zip"
    assert oi.tag_from_location(loc) == "v0.34.0"
    with pytest.raises(oi.InstallError):
        oi.tag_from_location("https://github.com/ollama/ollama/releases")


def test_sha256_for_reads_the_published_format():
    sums = (
        "e2b98770fb87f3b4c593c22f2e8eda59bcac1cd7b141f1388c4181a8bf271a72  ./OllamaSetup.exe\n"
        "5bb6b982f74184d4b67c1829fa76851ac849a2714bf3de506be41bb1860d3ce3  ./Ollama-darwin.zip\n"
    )
    assert oi.sha256_for(sums, "Ollama-darwin.zip").startswith("5bb6b982")
    with pytest.raises(oi.InstallError):
        oi.sha256_for(sums, "ollama-linux-amd64.tgz")


@pytest.mark.parametrize(
    ("plat", "machine", "expected"),
    [
        ("darwin", "arm64", "Ollama-darwin.zip"),
        ("darwin", "x86_64", "Ollama-darwin.zip"),
        ("win32", "AMD64", "OllamaSetup.exe"),
        ("win32", "ARM64", None),
        ("linux", "x86_64", None),
    ],
)
def test_asset_per_platform(monkeypatch, plat, machine, expected):
    monkeypatch.setattr(oi.sys, "platform", plat)
    monkeypatch.setattr(oi.platform, "machine", lambda: machine)
    assert oi.asset_name() == expected
    assert oi.supported() is (expected is not None)


def _transport(asset: str, payload: bytes, published_hash: str | None = None):
    digest = published_hash or hashlib.sha256(payload).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/latest/download/{asset}"):
            return httpx.Response(
                302,
                headers={
                    "location": f"https://github.com/ollama/ollama/releases/download/v9.9.9/{asset}"
                },
            )
        if path.endswith("/v9.9.9/sha256sum.txt"):
            return httpx.Response(200, text=f"{digest}  ./{asset}\n")
        if path.endswith(f"/v9.9.9/{asset}"):
            return httpx.Response(200, content=payload)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _collect(transport):
    async def run():
        return [e async for e in oi.install(transport=transport)]

    return asyncio.run(run())


@pytest.fixture
def fake_mac_zip(tmp_path):
    if sys.platform != "darwin":
        pytest.skip("需要 macOS 的 ditto")
    app = tmp_path / "src" / "Ollama.app" / "Contents"
    app.mkdir(parents=True)
    (app / "Info.plist").write_text("<plist/>")
    (app / "link").symlink_to("Info.plist")  # 符號連結要原樣保留
    archive = tmp_path / "Ollama-darwin.zip"
    subprocess.run(
        [
            "ditto",
            "-c",
            "-k",
            "--keepParent",
            str(tmp_path / "src" / "Ollama.app"),
            str(archive),
        ],
        check=True,
    )
    return archive.read_bytes()


def test_mac_install_downloads_verifies_copies_and_starts(
    monkeypatch, tmp_path, fake_mac_zip
):
    dest = tmp_path / "Applications"
    monkeypatch.setenv(oi.APP_DIR_ENV, str(dest))
    launched = []
    # 用狀態旗標而不是固定次數的迭代器：等待迴圈會問好幾次，迭代器用完時丟出的
    # StopIteration 進到 asyncio.to_thread 會讓 future 永遠等不到結果（踩過，測試卡死）。
    up = {"value": False}  # 裝完時還沒在跑 → 打開 app 之後就緒

    def launch(app):
        launched.append(app)
        up["value"] = True

    monkeypatch.setattr(oi, "api_ready", lambda timeout=2.0: up["value"])
    monkeypatch.setattr(oi, "ollama_app_running", lambda: False)
    monkeypatch.setattr(oi, "_launch", launch)
    monkeypatch.setattr(
        oi,
        "_start_server",
        lambda binary: pytest.fail("app 已經帶起伺服器，不該再跑 serve"),
    )

    events = _collect(_transport("Ollama-darwin.zip", fake_mac_zip))
    statuses = [e["status"] for e in events]

    assert statuses[0] == "resolving"
    assert "downloading" in statuses
    assert statuses[-4:] == ["verifying", "installing", "starting", "success"]
    assert events[-1]["version"] == "v9.9.9"
    app = dest / "Ollama.app"
    assert (app / "Contents" / "Info.plist").is_file()
    assert (app / "Contents" / "link").is_symlink(), "ditto 應保留符號連結"
    assert launched == [app]


def test_existing_app_is_not_overwritten(monkeypatch, tmp_path, fake_mac_zip):
    dest = tmp_path / "Applications"
    (dest / "Ollama.app").mkdir(parents=True)
    (dest / "Ollama.app" / "mine").write_text("user's own copy")
    monkeypatch.setenv(oi.APP_DIR_ENV, str(dest))
    monkeypatch.setattr(oi, "api_ready", lambda timeout=2.0: True)
    monkeypatch.setattr(oi, "_launch", lambda app: None)

    _collect(_transport("Ollama-darwin.zip", fake_mac_zip))
    assert (dest / "Ollama.app" / "mine").read_text() == "user's own copy"


def test_checksum_mismatch_stops_before_installing(monkeypatch, tmp_path):
    monkeypatch.setattr(oi.sys, "platform", "darwin")
    monkeypatch.setenv(oi.APP_DIR_ENV, str(tmp_path / "Applications"))
    monkeypatch.setattr(oi, "_install_mac", lambda *a: pytest.fail("不該安裝"))

    with pytest.raises(oi.InstallError, match="checksum"):
        _collect(_transport("Ollama-darwin.zip", b"tampered", published_hash="0" * 64))
    assert not (tmp_path / "Applications").exists()


def test_windows_runs_the_silent_installer(monkeypatch):
    monkeypatch.setattr(oi.sys, "platform", "win32")
    monkeypatch.setattr(oi.platform, "machine", lambda: "AMD64")
    ran = []
    monkeypatch.setattr(oi, "_run", lambda cmd, failure, timeout=600: ran.append(cmd))
    monkeypatch.setattr(oi, "api_ready", lambda timeout=2.0: True)  # 安裝程式自己會啟動
    monkeypatch.setattr(oi, "_launch", lambda app: pytest.fail("已經在跑就不該再開"))

    events = _collect(_transport("OllamaSetup.exe", b"MZ fake installer"))
    assert events[-1]["status"] == "success"
    assert ran and ran[0][1:] == [
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
        "/SP-",
    ]
    assert ran[0][0].endswith("OllamaSetup.exe")


def test_unsupported_platform_raises(monkeypatch):
    monkeypatch.setattr(oi.sys, "platform", "linux")
    with pytest.raises(oi.InstallError):
        _collect(None)


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(route.init_llm_config_route())
    monkeypatch.setattr(route, "_is_local_request", lambda request: True)
    return TestClient(app)


def test_endpoint_streams_events_and_errors(client, monkeypatch):
    async def ok(transport=None):
        yield {"status": "resolving"}
        yield {"status": "success", "version": "v1"}

    monkeypatch.setattr(route.ollama_installer, "install", ok)
    lines = client.post("/api/llm-config/ollama-install").text.strip().splitlines()
    assert [__import__("json").loads(x)["status"] for x in lines] == [
        "resolving",
        "success",
    ]

    async def boom(transport=None):
        yield {"status": "resolving"}
        raise oi.InstallError("nope")

    monkeypatch.setattr(route.ollama_installer, "install", boom)
    last = client.post("/api/llm-config/ollama-install").text.strip().splitlines()[-1]
    assert __import__("json").loads(last) == {"status": "error", "error": "nope"}


def test_endpoint_rejects_remote_requests(monkeypatch):
    app = FastAPI()
    app.include_router(route.init_llm_config_route())
    monkeypatch.setattr(route, "_is_local_request", lambda request: False)
    assert TestClient(app).post("/api/llm-config/ollama-install").status_code == 403


def test_falls_back_to_ollama_serve_when_the_app_does_not_start_it(
    monkeypatch, tmp_path, fake_mac_zip
):
    """乾淨的 macOS 上第一次打開 Ollama.app，伺服器可能一直沒起來（CI 實測）。"""
    monkeypatch.setenv(oi.APP_DIR_ENV, str(tmp_path / "Applications"))
    monkeypatch.setattr(oi, "APP_START_GRACE", 0.05)
    monkeypatch.setattr(oi, "POLL_INTERVAL", 0.01)
    binary = tmp_path / "ollama"
    binary.write_text("")
    monkeypatch.setattr(oi, "_serve_binary", lambda app: binary)
    up = {"value": False}
    served = []
    monkeypatch.setattr(oi, "api_ready", lambda timeout=2.0: up["value"])
    monkeypatch.setattr(oi, "ollama_app_running", lambda: False)
    monkeypatch.setattr(oi, "_launch", lambda app: None)  # app 打開了，伺服器卻沒起來

    def serve(path):
        served.append(path)
        up["value"] = True

    monkeypatch.setattr(oi, "_start_server", serve)

    events = _collect(_transport("Ollama-darwin.zip", fake_mac_zip))
    assert served == [binary]
    assert {"status": "starting", "fallback": "serve"} in events
    assert events[-1]["status"] == "success"


def test_serve_binary_points_inside_the_app_bundle(monkeypatch, tmp_path):
    monkeypatch.setattr(oi.sys, "platform", "darwin")
    app = tmp_path / "Ollama.app"
    assert oi._serve_binary(app) == app / "Contents" / "Resources" / "ollama"
    monkeypatch.setattr(oi.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert oi._serve_binary(None) == tmp_path / "Programs" / "Ollama" / "ollama.exe"


def _windows(monkeypatch):
    monkeypatch.setattr(oi.sys, "platform", "win32")
    monkeypatch.setattr(oi.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(oi, "_run", lambda cmd, failure, timeout=600: None)
    monkeypatch.setattr(oi, "POLL_INTERVAL", 0.01)
    monkeypatch.setattr(
        oi, "_start_server", lambda binary: pytest.fail("Windows 不該跑 serve 備案")
    )


def test_windows_waits_for_the_app_the_installer_started(monkeypatch):
    """使用者實際遇到：安裝程式開的 Ollama 還沒起來，我們又開一個 → 兩個 app 打架。"""
    _windows(monkeypatch)
    polls = {"n": 0}

    def ready(timeout=2.0):
        polls["n"] += 1
        return polls["n"] > 5  # 啟動得慢，問了幾次才就緒

    monkeypatch.setattr(oi, "api_ready", ready)
    monkeypatch.setattr(oi, "ollama_app_running", lambda: True)
    monkeypatch.setattr(
        oi, "_launch", lambda app: pytest.fail("安裝程式已經開了，不該再開一個")
    )

    events = _collect(_transport("OllamaSetup.exe", b"MZ fake installer"))
    assert events[-1]["status"] == "success"


def test_windows_reports_still_starting_instead_of_opening_another(monkeypatch):
    _windows(monkeypatch)
    monkeypatch.setattr(oi, "WINDOWS_START_TIMEOUT", 0.05)
    monkeypatch.setattr(oi, "api_ready", lambda timeout=2.0: False)
    monkeypatch.setattr(oi, "ollama_app_running", lambda: True)
    monkeypatch.setattr(
        oi, "_launch", lambda app: pytest.fail("app 還在跑，不該再開一個")
    )

    with pytest.raises(oi.InstallError, match="still starting"):
        _collect(_transport("OllamaSetup.exe", b"MZ fake installer"))


def test_windows_opens_the_app_once_when_nothing_is_running(monkeypatch):
    _windows(monkeypatch)
    monkeypatch.setattr(oi, "WINDOWS_START_TIMEOUT", 0.05)
    up = {"value": False}
    launched = []

    def launch(app):
        launched.append(app)
        up["value"] = True

    monkeypatch.setattr(oi, "api_ready", lambda timeout=2.0: up["value"])
    monkeypatch.setattr(oi, "ollama_app_running", lambda: False)
    monkeypatch.setattr(oi, "_launch", launch)

    events = _collect(_transport("OllamaSetup.exe", b"MZ fake installer"))
    assert events[-1]["status"] == "success"
    assert len(launched) == 1


def test_mac_does_not_open_a_second_app(monkeypatch, tmp_path, fake_mac_zip):
    monkeypatch.setenv(oi.APP_DIR_ENV, str(tmp_path / "Applications"))
    monkeypatch.setattr(oi, "POLL_INTERVAL", 0.01)
    polls = {"n": 0}

    def ready(timeout=2.0):
        polls["n"] += 1
        return polls["n"] > 3

    monkeypatch.setattr(oi, "api_ready", ready)
    monkeypatch.setattr(oi, "ollama_app_running", lambda: True)
    monkeypatch.setattr(
        oi, "_launch", lambda app: pytest.fail("已經有 app 在跑，不該再開")
    )

    events = _collect(_transport("Ollama-darwin.zip", fake_mac_zip))
    assert events[-1]["status"] == "success"


@pytest.mark.parametrize(
    ("plat", "procs", "expected"),
    [
        (
            "darwin",
            [
                {
                    "name": "Ollama",
                    "exe": "/Applications/Ollama.app/Contents/MacOS/Ollama",
                }
            ],
            True,
        ),
        # ollama serve 是 app 帶起來的伺服器，不是 app 本體
        (
            "darwin",
            [
                {
                    "name": "ollama",
                    "exe": "/Applications/Ollama.app/Contents/Resources/ollama",
                }
            ],
            False,
        ),
        (
            "win32",
            [
                {
                    "name": "ollama app.exe",
                    "exe": "C:\\Users\\u\\AppData\\Local\\Programs\\Ollama\\ollama app.exe",
                }
            ],
            True,
        ),
        (
            "win32",
            [
                {
                    "name": "ollama.exe",
                    "exe": "C:\\Users\\u\\AppData\\Local\\Programs\\Ollama\\ollama.exe",
                }
            ],
            False,
        ),
        ("win32", [], False),
    ],
)
def test_ollama_app_running_tells_the_app_from_the_server(
    monkeypatch, plat, procs, expected
):
    from types import SimpleNamespace

    monkeypatch.setattr(oi.sys, "platform", plat)
    monkeypatch.setattr(
        oi.psutil,
        "process_iter",
        lambda attrs=None: [SimpleNamespace(info=p) for p in procs],
    )
    assert oi.ollama_app_running() is expected
