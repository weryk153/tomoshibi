"""conf.yaml 的換行符必須原樣往返。

read_conf_lines 與 write_conf 原本都用 Python 預設的 universal newlines：讀進來
CRLF 被轉成 LF，寫出去 LF 又被轉成 os.linesep。在 Windows 上，一份 LF 的
conf.yaml 存一次就整份變 CRLF——改一個欄位卻產生整份 diff，正好違反 conf_editor
自己立的規矩（「其餘每一行、每一個註解都原樣保留」）。

加上 newline="" 之後換行行為不再依賴平台，所以這份測試在 Linux CI 上就釘得住
一個原本只有 Windows 使用者踩得到的 bug。
"""

import pytest

from src.open_llm_vtuber import conf_editor


@pytest.fixture
def conf_at(tmp_path, monkeypatch):
    """把 CONF_PATH 指到 tmp_path 底下的一份檔案，內容由呼叫端決定。"""

    def _make(raw: bytes) -> str:
        path = tmp_path / "conf.yaml"
        path.write_bytes(raw)
        monkeypatch.setattr(conf_editor, "CONF_PATH", str(path))
        return str(path)

    return _make


LF = b"system_config:\n  host: '127.0.0.1'\n  port: 12393\n"
CRLF = b"system_config:\r\n  host: '127.0.0.1'\r\n  port: 12393\r\n"


def test_lf_file_stays_lf(conf_at):
    path = conf_at(LF)
    lines = conf_editor.read_conf_lines()
    conf_editor.write_conf(lines)
    assert open(path, "rb").read() == LF


def test_crlf_file_stays_crlf(conf_at):
    path = conf_at(CRLF)
    lines = conf_editor.read_conf_lines()
    conf_editor.write_conf(lines)
    assert open(path, "rb").read() == CRLF


def test_edited_lf_file_only_changes_the_edited_line(conf_at):
    """真正要防的東西：改一個欄位不該動到其他行的換行符。"""
    path = conf_at(LF)
    lines = conf_editor.read_conf_lines()
    start, end = conf_editor.system_config_extent(lines)
    conf_editor.rewrite_str_leaf(lines, start, end, "host", "0.0.0.0")
    conf_editor.write_conf(lines)

    raw = open(path, "rb").read()
    assert b"\r\n" not in raw, "LF 檔案被轉成了 CRLF"
    assert b"0.0.0.0" in raw
    assert raw.count(b"\n") == LF.count(b"\n"), "行數變了"
