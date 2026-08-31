"""conf.yaml 的外科手術式編輯——重寫前的特徵測試。

conf.yaml 是使用者手寫、帶滿註解的檔案。設定頁存檔時不能整份重新序列化（那會
把註解、順序、縮排全部洗掉），只能就地改掉指定的那一行。

這些行為原本散在三個模組裡：translator_route 定義區塊定位與純量寫入、
memory_route 定義整數與 upsert、perf_route 跨模組借用兩邊。契約在這裡釘住，
之後不管誰擁有實作都要通過。
"""

import re

import pytest

from src.open_llm_vtuber import conf_editor as ce


NESTED = """\
character_config:
  asr_config:
    asr_model: 'sherpa_onnx_asr'
    groq_whisper_asr:
      api_key: 'groq-key'
    azure_asr:
      api_key: 'azure-key'
      region: 'eastus'
  tts_config:
    tts_model: 'edge_tts'
    azure_tts:
      api_key: 'tts-key'
"""


CONF = """\
system_config:
  port: 12393
  # 底下是角色設定
character_config:
  conf_uid: kurisu
  long_term_memory_enabled: True  # 開著
  core_memory_max_chars: 1500
  tts_preprocessor_config:
    translator_config:
      translate_audio: False
"""


@pytest.fixture()
def conf(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(CONF, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    return path


def _lines(conf):
    return conf.read_text(encoding="utf-8").splitlines(keepends=True)


# --- 區塊定位 ----------------------------------------------------------------


def test_block_extent_covers_only_the_indented_children(conf):
    lines = _lines(conf)
    start, indent, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )

    assert lines[start].startswith("character_config:")
    assert indent == 0
    # 區塊到檔尾（後面沒有同層級的鍵）
    assert end == len(lines)


def test_block_extent_stops_at_the_next_sibling(conf):
    lines = _lines(conf)
    start, _, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)system_config:\s*(#.*)?$")
    )

    # system_config 的區塊在 character_config 那行前面就結束
    assert "".join(lines[start:end]).count("character_config") == 0


def test_missing_block_returns_nones(conf):
    result = ce.find_block_extent(_lines(conf), re.compile(r"^(\s*)nope:\s*$"))

    assert result == (None, None, None)


def test_nested_block_can_be_found_from_an_offset(conf):
    lines = _lines(conf)
    _, _, _ = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )
    start, indent, _ = ce.find_block_extent(
        lines, re.compile(r"^(\s*)translator_config:\s*(#.*)?$")
    )

    assert indent == 4


# --- 改寫葉節點 --------------------------------------------------------------


def test_bool_leaf_is_written_bare_not_quoted(conf):
    # 加引號會讓 Pydantic 把 'True' 讀成字串。
    lines = _lines(conf)
    start, _, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )

    assert ce.rewrite_bool_leaf(lines, start, end, "long_term_memory_enabled", False)
    assert "  long_term_memory_enabled: False" in "".join(lines)


def test_inline_comment_survives_a_rewrite(conf):
    lines = _lines(conf)
    start, _, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )
    ce.rewrite_bool_leaf(lines, start, end, "long_term_memory_enabled", False)

    assert "# 開著" in "".join(lines)


def test_int_leaf_is_written_bare(conf):
    lines = _lines(conf)
    start, _, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )

    assert ce.rewrite_int_leaf(lines, start, end, "core_memory_max_chars", 3000)
    assert "  core_memory_max_chars: 3000" in "".join(lines)


def test_rewrite_reports_false_when_the_leaf_is_absent(conf):
    lines = _lines(conf)
    start, _, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )

    assert ce.rewrite_int_leaf(lines, start, end, "not_there", 1) is False


# --- upsert（不存在就補上）---------------------------------------------------


def test_upsert_inserts_a_missing_leaf_with_matching_indent(conf):
    # UI 開得出來的設定就該存得下去。使用者從沒手動加過那行不是不能存的理由。
    lines = _lines(conf)
    start, _, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )

    ce.upsert_leaf(lines, start + 1, end, "memory_consolidation_interval", "3")
    text = "".join(lines)

    assert "  memory_consolidation_interval: 3" in text
    # 既有內容一個字都沒被動到
    assert "  conf_uid: kurisu" in text
    assert "# 底下是角色設定" in text


def test_upsert_rewrites_when_the_leaf_already_exists(conf):
    lines = _lines(conf)
    start, _, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )

    ce.upsert_leaf(lines, start + 1, end, "core_memory_max_chars", "2000")
    text = "".join(lines)

    assert "  core_memory_max_chars: 2000" in text
    assert text.count("core_memory_max_chars") == 1


def test_result_still_parses_as_yaml(conf):
    from ruamel.yaml import YAML

    lines = _lines(conf)
    start, _, end = ce.find_block_extent(
        lines, re.compile(r"^(\s*)character_config:\s*(#.*)?$")
    )
    ce.upsert_leaf(lines, start + 1, end, "memory_consolidation_interval", "5")
    ce.rewrite_bool_leaf(lines, start, end, "long_term_memory_enabled", False)
    conf.write_text("".join(lines), encoding="utf-8")

    data = YAML(typ="safe").load(conf.read_text(encoding="utf-8"))

    assert data["character_config"]["memory_consolidation_interval"] == 5
    assert data["character_config"]["long_term_memory_enabled"] is False
    assert data["system_config"]["port"] == 12393


# --- 寫檔 --------------------------------------------------------------------


def test_write_is_atomic_and_backs_up_once(conf):
    ce.write_conf(["changed\n"])

    assert conf.read_text(encoding="utf-8") == "changed\n"
    backup = conf.parent / "conf.yaml.bak"
    assert backup.read_text(encoding="utf-8") == CONF
    assert not list(conf.parent.glob("*.tmp"))

    # 第二次寫入不可以覆蓋備份——備份的價值是「使用者原本的那一份」。
    ce.write_conf(["changed again\n"])
    assert backup.read_text(encoding="utf-8") == CONF


# --- 具名區塊 ----------------------------------------------------------------


def test_block_extent_by_name(conf):
    lines = _lines(conf)
    start, end = ce.system_config_extent(lines)

    body = "".join(lines[start:end])
    assert "port: 12393" in body
    assert "character_config" not in body


def test_named_block_can_start_from_an_offset(conf):
    lines = _lines(conf)
    cc_start, _ = ce.character_config_extent(lines)
    start, end = ce.block_extent(lines, "translator_config", start_from=cc_start)

    assert "translate_audio: False" in "".join(lines[start:end])


def test_missing_named_block_raises_with_the_key_in_the_message(conf):
    # 找不到就丟，不要回 None 讓呼叫端拿去切片——那時的錯誤訊息跟真正的原因無關。
    with pytest.raises(KeyError, match="nope"):
        ce.block_extent(_lines(conf), "nope")


# --- 子區塊要限定在父區塊之內 -------------------------------------------------


def test_sub_block_is_scoped_to_its_parent(tmp_path, monkeypatch):
    """同名的葉節點在別的引擎底下也有——沒有限定範圍就會改到隔壁的。

    asr_config.azure_asr.api_key 與 tts_config.azure_tts.api_key 都叫 api_key。
    改語音辨識的金鑰卻寫進語音合成那塊，是不會有任何徵兆的那種錯。
    """
    path = tmp_path / "conf.yaml"
    path.write_text(NESTED, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    asr_start, asr_end = ce.block_extent(lines, "asr_config")
    start, end = ce.sub_block_extent(lines, asr_start, asr_end, "azure_asr")

    assert ce.rewrite_str_leaf(lines, start, end, "api_key", "changed")
    text = "".join(lines)

    assert "api_key: 'changed'" in text
    # 隔壁的 tts 金鑰一個字都沒動
    assert "api_key: 'tts-key'" in text


def test_sub_block_outside_the_parent_is_not_found(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(NESTED, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    asr_start, asr_end = ce.block_extent(lines, "asr_config")
    # azure_tts 在 tts_config 底下，從 asr_config 的範圍看不到它。
    assert ce.sub_block_extent(lines, asr_start, asr_end, "azure_tts") == (None, None)


def test_nested_extent_drills_a_whole_path(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(NESTED, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    start, end = ce.nested_extent(lines, "character_config", "asr_config", "azure_asr")

    assert "region: 'eastus'" in "".join(lines[start:end])
    assert "tts" not in "".join(lines[start:end])


def test_nested_extent_says_which_level_is_missing(tmp_path, monkeypatch):
    path = tmp_path / "conf.yaml"
    path.write_text(NESTED, encoding="utf-8")
    monkeypatch.setattr(ce, "CONF_PATH", str(path))
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)

    with pytest.raises(KeyError, match="nope"):
        ce.nested_extent(lines, "character_config", "asr_config", "nope")
