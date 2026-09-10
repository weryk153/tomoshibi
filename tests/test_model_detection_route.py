"""偵測端點與套用端點。

這一層只負責串：probe 拿清單、profile 決定要不要加必要設定、
write_provider_config 落地。決定與寫入的正確性各自有測試釘著，這裡釘的是接線
和降級行為。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.open_llm_vtuber import llm_config_route as route
from src.open_llm_vtuber import conf_editor
from src.open_llm_vtuber.model_probe import DetectedModel

CONF = """character_config:
  agent_config:
    agent_settings:
      basic_memory_agent:
        llm_provider: 'openai_compatible_llm'
        use_mcpp: true
    llm_configs:
      openai_compatible_llm:
        base_url: 'http://localhost:11434/v1'
        model: 'placeholder'
        llm_api_key: 'somethingelse'
      ollama_llm:
        base_url: 'http://localhost:11434/v1'
        model: 'qwen2.5:3b'
      lmstudio_llm:
        base_url: 'http://localhost:1234/v1'
        model: 'qwen2.5:3b'
"""

LMS = DetectedModel(
    id="qwen/qwen3.5-9b",
    backend="lmstudio",
    base_url="http://127.0.0.1:1234/v1",
    arch="qwen35",
    is_vlm=True,
    supports_tools=True,
    max_context=262144,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(conf_editor, "CONF_PATH", str(path))
    # write_provider_config 在動手前會用 route.CONF_PATH 驗證區塊存在
    # （_validate_path_with_ruamel）；不跟著指向同一份暫存檔的話，驗證會打開
    # 專案根目錄下（若存在）那份真正的 conf.yaml，跟這裡的測試資料對不上，
    # 在沒有那份檔案的環境（例如 CI，conf.yaml 不進版控）甚至會直接炸開。
    # 既有的 tests/test_write_provider_config.py 也是這樣兩個都設。
    monkeypatch.setattr(route, "CONF_PATH", str(path), raising=False)
    app = FastAPI()
    app.include_router(route.init_llm_config_route())
    monkeypatch.setattr(route, "_is_local_request", lambda request: True)
    return TestClient(app), path


def test_detect_merges_both_backends(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(route, "probe_lmstudio", lambda base_url: (True, [LMS]))
    monkeypatch.setattr(
        route,
        "probe_ollama",
        lambda base_url: (
            True,
            [DetectedModel(id="qwen3:8b", backend="ollama", base_url=base_url)],
        ),
    )
    body = c.get("/api/llm-config/detect").json()
    ids = [m["id"] for m in body["models"]]
    assert ids == ["qwen/qwen3.5-9b", "qwen3:8b"]
    assert body["lmstudio_available"] is True
    assert body["ollama_available"] is True


def test_detect_survives_both_backends_being_down(client, monkeypatch):
    """都沒在跑不是錯誤——精靈要能顯示「請先裝一個」而不是白畫面。"""
    c, _ = client
    monkeypatch.setattr(route, "probe_lmstudio", lambda base_url: (False, []))
    monkeypatch.setattr(route, "probe_ollama", lambda base_url: (False, []))
    resp = c.get("/api/llm-config/detect")
    assert resp.status_code == 200
    body = resp.json()
    assert body["models"] == []
    assert body["lmstudio_available"] is False
    assert body["ollama_available"] is False
    assert body["recommended_pull"]  # 仍要給得出下載建議


def test_detect_ollama_reachable_but_no_models(client, monkeypatch):
    """R17 修的那個 bug：daemon 在跑但一顆模型都沒有，不能跟「根本沒裝」回傳
    同一個 ollama_available=False——這兩種情況前端要給完全不同的建議
    （「去下載一個模型」vs「去把 Ollama 打開」），過去用 bool(models) 算旗標
    時分不出來。"""
    c, _ = client
    monkeypatch.setattr(route, "probe_lmstudio", lambda base_url: (False, []))
    monkeypatch.setattr(route, "probe_ollama", lambda base_url: (True, []))
    body = c.get("/api/llm-config/detect").json()
    assert body["models"] == []
    assert body["ollama_available"] is True
    assert body["lmstudio_available"] is False


def test_detect_lmstudio_reachable_but_no_models(client, monkeypatch):
    """理由同上一條，換成 LM Studio 這邊可達但沒有模型。"""
    c, _ = client
    monkeypatch.setattr(route, "probe_lmstudio", lambda base_url: (True, []))
    monkeypatch.setattr(route, "probe_ollama", lambda base_url: (False, []))
    body = c.get("/api/llm-config/detect").json()
    assert body["models"] == []
    assert body["lmstudio_available"] is True
    assert body["ollama_available"] is False


def test_apply_writes_model_and_profile(client, monkeypatch):
    c, path = client
    monkeypatch.setattr(route, "list_lmstudio_models", lambda base_url: [LMS])
    monkeypatch.setattr(route, "list_ollama_models", lambda base_url: [])
    monkeypatch.setattr(route, "_validate_combo", _ok_validate)

    body = c.post(
        "/api/llm-config/apply-detected",
        json={"backend": "lmstudio", "model": "qwen/qwen3.5-9b"},
    ).json()

    assert body["ok"] is True
    text = path.read_text(encoding="utf-8")
    assert "model: 'qwen/qwen3.5-9b'" in text
    assert "llm_provider: 'lmstudio_llm'" in text
    assert "reasoning_effort: 'none'" in text
    assert "timeout" in body["note"], "要把 profile 的 note 交給前端顯示"


def test_apply_without_a_profile_still_succeeds(client, monkeypatch):
    """查不到 profile 只代表不加必要設定，不代表設定失敗。"""
    c, path = client
    plain = DetectedModel(
        id="llama3:8b",
        backend="lmstudio",
        base_url="http://127.0.0.1:1234/v1",
        arch="llama",
    )
    monkeypatch.setattr(route, "list_lmstudio_models", lambda base_url: [plain])
    monkeypatch.setattr(route, "list_ollama_models", lambda base_url: [])
    monkeypatch.setattr(route, "_validate_combo", _ok_validate)

    body = c.post(
        "/api/llm-config/apply-detected",
        json={"backend": "lmstudio", "model": "llama3:8b"},
    ).json()
    assert body["ok"] is True
    assert body["note"] is None
    assert "extra_body" not in path.read_text(encoding="utf-8")


def test_apply_syncs_use_mcpp_with_tool_support(client, monkeypatch):
    """工具能力偵測得到就別讓使用者猜。不支援卻開著＝每輪白付 mcp_prompt 的
    ~388 token 加上工具 schema，而模型只會忽略它們。"""
    c, path = client
    no_tools = DetectedModel(
        id="plain:8b",
        backend="lmstudio",
        base_url="http://127.0.0.1:1234/v1",
        arch="llama",
        supports_tools=False,
    )
    monkeypatch.setattr(route, "list_lmstudio_models", lambda base_url: [no_tools])
    monkeypatch.setattr(route, "list_ollama_models", lambda base_url: [])
    monkeypatch.setattr(route, "_validate_combo", _ok_validate)

    c.post(
        "/api/llm-config/apply-detected",
        json={"backend": "lmstudio", "model": "plain:8b"},
    )
    assert "use_mcpp: False" in path.read_text(encoding="utf-8")


def test_apply_enables_use_mcpp_for_a_tool_capable_model(client, monkeypatch):
    c, path = client
    monkeypatch.setattr(route, "list_lmstudio_models", lambda base_url: [LMS])
    monkeypatch.setattr(route, "list_ollama_models", lambda base_url: [])
    monkeypatch.setattr(route, "_validate_combo", _ok_validate)

    c.post(
        "/api/llm-config/apply-detected",
        json={"backend": "lmstudio", "model": "qwen/qwen3.5-9b"},
    )
    assert "use_mcpp: True" in path.read_text(encoding="utf-8")


def test_apply_blocks_when_validation_fails(client, monkeypatch):
    """唯一不 fail-soft 的地方：讓使用者以為設好了但其實不能用，比報錯更糟。"""
    c, path = client
    monkeypatch.setattr(route, "list_lmstudio_models", lambda base_url: [LMS])
    monkeypatch.setattr(route, "list_ollama_models", lambda base_url: [])

    async def _fail(base_url, model, api_key):
        return False, "Model not found."

    monkeypatch.setattr(route, "_validate_combo", _fail)

    resp = c.post(
        "/api/llm-config/apply-detected",
        json={"backend": "lmstudio", "model": "qwen/qwen3.5-9b"},
    )
    assert resp.json()["ok"] is False
    assert "model: 'qwen2.5:3b'" in path.read_text(encoding="utf-8"), "驗證失敗還是寫了"


def test_apply_rejects_a_model_that_was_not_detected(client, monkeypatch):
    """model 是請求可控的，不能拿它去組任何東西之前先確認它真的存在。"""
    c, _ = client
    monkeypatch.setattr(route, "list_lmstudio_models", lambda base_url: [LMS])
    monkeypatch.setattr(route, "list_ollama_models", lambda base_url: [])
    resp = c.post(
        "/api/llm-config/apply-detected",
        json={"backend": "lmstudio", "model": "../../etc/passwd"},
    )
    assert resp.json()["ok"] is False


def test_apply_ollama_describe_failure_leaves_use_mcpp_untouched(client, monkeypatch):
    """describe_ollama_model 失敗（逾時、Ollama 正在載入大模型時的暫時性
    500）代表「還沒問到」，不是「沒有工具」。沿用列表階段 supports_tools=False
    這個預設值去覆寫 use_mcpp，會把使用者自己在 Settings 開的開關悄悄關掉——
    這裡釘住修好之後的行為：問不到就完全不碰 use_mcpp。"""
    c, path = client
    listed = DetectedModel(
        id="qwen2.5:3b",
        backend="ollama",
        base_url="http://localhost:11434/v1",
        arch="qwen2",
        supports_tools=False,
    )
    monkeypatch.setattr(route, "list_lmstudio_models", lambda base_url: [])
    monkeypatch.setattr(route, "list_ollama_models", lambda base_url: [listed])
    monkeypatch.setattr(route, "describe_ollama_model", lambda base_url, model_id: None)
    monkeypatch.setattr(route, "_validate_combo", _ok_validate)

    before = path.read_text(encoding="utf-8")
    assert "use_mcpp: true" in before  # CONF fixture 裡使用者原本開著

    body = c.post(
        "/api/llm-config/apply-detected",
        json={"backend": "ollama", "model": "qwen2.5:3b"},
    ).json()

    assert body["ok"] is True
    after = path.read_text(encoding="utf-8")
    assert "use_mcpp: true" in after, "describe 失敗不該覆寫使用者原本的 use_mcpp"
    assert "model: 'qwen2.5:3b'" in after, "provider 區塊本身還是要照樣寫入"


def test_apply_rejects_model_id_with_control_characters(client, monkeypatch):
    """model id 會被逐字寫進 conf.yaml；換行之類的控制字元混進去就能在寫檔時
    多插出任意一行 YAML。這條路今天只有本機推論端能觸發（id 要跟偵測清單裡
    的一模一樣才會比對上），但堵起來不必去信任它回報的字串長什麼樣子。"""
    c, path = client
    evil = DetectedModel(
        id="qwen2.5:3b\nlm_provider: 'ollama_llm'",
        backend="lmstudio",
        base_url="http://127.0.0.1:1234/v1",
        arch="qwen2",
    )
    monkeypatch.setattr(route, "list_lmstudio_models", lambda base_url: [evil])
    monkeypatch.setattr(route, "list_ollama_models", lambda base_url: [])

    before = path.read_text(encoding="utf-8")
    resp = c.post(
        "/api/llm-config/apply-detected",
        json={"backend": "lmstudio", "model": evil.id},
    )
    assert resp.json()["ok"] is False
    assert path.read_text(encoding="utf-8") == before, "拒絕時完全不該碰檔案"


async def _ok_validate(base_url, model, api_key):
    return True, ""


def test_detect_reports_installed_but_not_running(client, monkeypatch):
    """連不上 Ollama 時，要分得出「沒裝」和「裝了沒開」——兩者給使用者的建議不同。"""
    c, _ = client
    monkeypatch.setattr(route, "probe_lmstudio", lambda base_url: (False, []))
    monkeypatch.setattr(route, "probe_ollama", lambda base_url: (False, []))

    monkeypatch.setattr(route, "ollama_installed", lambda: True)
    body = c.get("/api/llm-config/detect").json()
    assert body["ollama_available"] is False
    assert body["ollama_installed"] is True

    monkeypatch.setattr(route, "ollama_installed", lambda: False)
    assert c.get("/api/llm-config/detect").json()["ollama_installed"] is False


def test_detect_running_ollama_counts_as_installed(client, monkeypatch):
    c, _ = client
    monkeypatch.setattr(route, "probe_lmstudio", lambda base_url: (False, []))
    monkeypatch.setattr(route, "probe_ollama", lambda base_url: (True, []))
    monkeypatch.setattr(route, "ollama_installed", lambda: False)
    assert c.get("/api/llm-config/detect").json()["ollama_installed"] is True


def test_ollama_installed_finds_the_cli_or_the_app(monkeypatch, tmp_path):
    from src.open_llm_vtuber import model_probe

    monkeypatch.setattr(
        model_probe.shutil, "which", lambda name: "/usr/local/bin/ollama"
    )
    assert model_probe.ollama_installed() is True

    monkeypatch.setattr(model_probe.shutil, "which", lambda name: None)
    monkeypatch.setattr(model_probe.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert model_probe.ollama_installed() is False
    app = tmp_path / "Programs" / "Ollama" / "ollama app.exe"
    app.parent.mkdir(parents=True)
    app.write_bytes(b"")
    assert model_probe.ollama_installed() is True
