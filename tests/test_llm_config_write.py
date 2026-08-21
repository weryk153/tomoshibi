"""LLM 設定的寫入——重寫前的特徵測試。

首次設定精靈就是靠這條路把使用者填的端點、模型、金鑰寫進 conf.yaml。它同時要
把 llm_provider 指向 openai_compatible_llm，否則使用者填完精靈，程式還是連著
別的供應商。

契約：

- 只改那三個葉節點，其餘每一行、每一個註解、每一個布林的大小寫原樣不動。
- llm_provider 一起改過去——只寫了端點卻沒切供應商，等於白填。
- 結構不對時在寫任何東西之前就失敗，不留下改到一半的設定檔。
"""

import pytest
from ruamel.yaml import YAML

from src.open_llm_vtuber import conf_editor as ce
from src.open_llm_vtuber import llm_config_route as lc


CONF = """\
system_config:
  port: 12393
character_config:
  agent_config:
    agent_settings:
      basic_memory_agent:
        llm_provider: 'ollama_llm'  # 目前用哪一個
        faster_first_response: True
    llm_configs:
      openai_compatible_llm:
        base_url: 'http://localhost:11434/v1'  # 端點
        llm_api_key: 'old-key'
        model: 'qwen2.5:3b'
        organization_id: null
        temperature: 1.0
      ollama_llm:
        base_url: 'http://localhost:11434/v1'
        model: 'qwen2.5:3b'
"""


@pytest.fixture()
def conf(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(lc, "CONF_PATH", str(path))
    return path


def _parsed(conf):
    return YAML(typ="safe").load(conf.read_text(encoding="utf-8"))


def _openai(conf):
    return _parsed(conf)["character_config"]["agent_config"]["llm_configs"][
        "openai_compatible_llm"
    ]


def test_the_three_leaves_are_written(conf):
    lc._write_openai_block("http://127.0.0.1:1234/v1", "my-model", "sk-secret")
    block = _openai(conf)

    assert block["base_url"] == "http://127.0.0.1:1234/v1"
    assert block["model"] == "my-model"
    assert block["llm_api_key"] == "sk-secret"


def test_neighbouring_leaves_and_literals_are_untouched(conf):
    lc._write_openai_block("http://127.0.0.1:1234/v1", "my-model", "sk-secret")
    block = _openai(conf)
    text = conf.read_text(encoding="utf-8")

    assert block["organization_id"] is None
    assert block["temperature"] == 1.0
    # ruamel 全份重新序列化會把 True 正規化成 true、null 變空——這裡不能發生。
    assert "faster_first_response: True" in text
    assert "organization_id: null" in text


def test_inline_comments_survive(conf):
    lc._write_openai_block("http://127.0.0.1:1234/v1", "my-model", "sk-secret")
    text = conf.read_text(encoding="utf-8")

    assert "# 端點" in text
    assert "# 目前用哪一個" in text


def test_the_sibling_provider_block_is_untouched(conf):
    lc._write_openai_block("http://127.0.0.1:1234/v1", "my-model", "sk-secret")
    ollama = _parsed(conf)["character_config"]["agent_config"]["llm_configs"][
        "ollama_llm"
    ]

    # base_url／model 在兩個區塊裡同名，寫錯地方不會有任何徵兆。
    assert ollama["model"] == "qwen2.5:3b"


def test_provider_is_switched_over(conf):
    lines = conf.read_text(encoding="utf-8").splitlines(keepends=True)
    lc._point_llm_provider_at_openai_compatible(lines)
    conf.write_text("".join(lines), encoding="utf-8")

    agent = _parsed(conf)["character_config"]["agent_config"]["agent_settings"][
        "basic_memory_agent"
    ]
    assert agent["llm_provider"] == "openai_compatible_llm"


def test_switching_the_provider_keeps_its_comment(conf):
    lines = conf.read_text(encoding="utf-8").splitlines(keepends=True)
    lc._point_llm_provider_at_openai_compatible(lines)

    assert "# 目前用哪一個" in "".join(lines)


def test_a_broken_structure_fails_before_writing(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text("system_config:\n  port: 1\n", encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    monkeypatch.setattr(lc, "CONF_PATH", str(path))
    before = path.read_text(encoding="utf-8")

    with pytest.raises(Exception):
        lc._write_openai_block("http://x/v1", "m", "k")

    assert path.read_text(encoding="utf-8") == before
