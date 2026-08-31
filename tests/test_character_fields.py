"""GET /api/characters 必須回傳 live2d_model_name。

PUT 要求這個欄位且缺了回 400，所以編輯表單需要它來預填。少了它，
使用者每次編輯都被迫重選皮膚。
"""

from src.open_llm_vtuber.character_route import _read_character_fields


def test_read_character_fields_includes_live2d_model_name(tmp_path, monkeypatch):
    # _read_character_fields -> read_yaml() routes every path through
    # safe_join(os.getcwd(), config_path), a path-traversal guard that
    # confines reads to the project root (same as CONF_PATH = "conf.yaml"
    # and characters/*.yaml being referenced relative to cwd in production).
    # An absolute tmp_path passed directly would trip that guard with
    # ValueError before ever reaching the live2d_model_name logic, so we
    # chdir into tmp_path and use a relative filename instead.
    monkeypatch.chdir(tmp_path)
    conf = tmp_path / "conf.yaml"
    conf.write_text(
        "character_config:\n"
        "  conf_name: '測試角色'\n"
        "  conf_uid: 'test_001'\n"
        "  character_name: '小測'\n"
        "  persona_prompt: '你是一個測試用的角色。'\n"
        "  live2d_model_name: 'mao_pro'\n",
        encoding="utf-8",
    )

    fields = _read_character_fields("conf.yaml", is_base=True)

    assert fields is not None
    assert fields["live2d_model_name"] == "mao_pro", (
        "GET 必須回傳目前的皮膚，否則編輯表單無法預填，而 PUT 缺這個欄位會回 400"
    )
