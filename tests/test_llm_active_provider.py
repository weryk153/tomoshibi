"""GET /api/llm-config reports which provider is actually in use.

This route reads and writes `openai_compatible_llm` unconditionally, but the
agent uses whichever block `llm_provider` names. When those differ, the settings
tab shows a base_url and model that nothing is using, and anything the user
edits there silently fails to reach the conversation — the same trap as a
character pinning its own TTS engine.

Observed live: llm_provider was `lmstudio_llm` (LM Studio on :1234 serving
qwen/qwen3.5-9b) while the tab displayed the untouched openai_compatible_llm
block pointing at Ollama on :11434 with qwen2.5:3b — a server that was not even
running.

Same convention as tests/test_llm_provider_write.py: call the route module's
helpers directly against a tmp_path conf.yaml, never a real request.
"""

from src.open_llm_vtuber.llm_config_route import _get_llm_provider
from src.open_llm_vtuber.config_manager.utils import read_yaml


def _write_conf(tmp_path, monkeypatch, llm_provider_line: str) -> dict:
    # read_yaml refuses absolute paths outside the project root, so read it the
    # same way the app does: from the current directory.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "conf.yaml").write_text(
        "character_config:\n"
        "  agent_config:\n"
        "    agent_settings:\n"
        "      basic_memory_agent:\n"
        f"{llm_provider_line}"
        "    llm_configs:\n"
        "      openai_compatible_llm:\n"
        "        base_url: 'http://localhost:11434/v1'\n"
        "        model: 'qwen2.5:3b'\n"
        "        llm_api_key: 'somekey'\n",
        encoding="utf-8",
    )
    return read_yaml("conf.yaml")


def test_reports_a_provider_that_is_not_the_edited_block(tmp_path, monkeypatch):
    data = _write_conf(tmp_path, monkeypatch, "        llm_provider: 'lmstudio_llm'\n")

    assert _get_llm_provider(data) == "lmstudio_llm"


def test_reports_the_edited_block_when_they_agree(tmp_path, monkeypatch):
    """No warning must appear in the common case, or it becomes background noise."""
    data = _write_conf(
        tmp_path, monkeypatch, "        llm_provider: 'openai_compatible_llm'\n"
    )

    assert _get_llm_provider(data) == "openai_compatible_llm"


def test_missing_selector_is_reported_as_absent_rather_than_guessed(
    tmp_path, monkeypatch
):
    """The caller defaults to openai_compatible_llm; this helper must not lie
    about a selector that is not there, or a genuinely broken config would look
    deliberate."""
    data = _write_conf(tmp_path, monkeypatch, "        conf_name: 'x'\n")

    assert _get_llm_provider(data) is None
