"""存檔 LLM 設定時必須同時把 llm_provider 指向 openai_compatible_llm。

缺了這一步，在 llm_provider 指向別的區塊（例如 lmstudio_llm）的機器上，
存檔會成功但完全不生效，且沒有任何錯誤訊息。
"""

from src.open_llm_vtuber.llm_config_route import _write_openai_block


def test_write_openai_block_also_points_llm_provider_at_it(tmp_path, monkeypatch):
    conf = tmp_path / "conf.yaml"
    conf.write_text(
        "character_config:\n"
        "  agent_config:\n"
        "    conversation_agent_choice: 'basic_memory_agent'\n"
        "    agent_settings:\n"
        "      basic_memory_agent:\n"
        "        llm_provider: 'lmstudio_llm'\n"
        "    llm_configs:\n"
        "      openai_compatible_llm:\n"
        "        base_url: 'http://old'\n"
        "        model: 'old-model'\n"
        "        llm_api_key: 'old-key'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    _write_openai_block("http://new", "new-model", "new-key")

    text = conf.read_text(encoding="utf-8")
    assert "openai_compatible_llm" in text
    assert "new-model" in text
    assert "llm_provider: 'openai_compatible_llm'" in text or \
           'llm_provider: "openai_compatible_llm"' in text, \
        "llm_provider 必須被指向 openai_compatible_llm，否則存檔不生效"


def test_is_configured_respects_llm_provider(tmp_path, monkeypatch):
    """llm_provider 指向別的區塊時，不得因為 openai 區塊是佔位符就說「未設定」。

    開發機的實際狀態：llm_provider: 'lmstudio_llm' 且 LLM 可正常運作，但
    _is_configured 只看 openai_compatible_llm 區塊，回報 False——首次精靈因此
    會在每次啟動時彈出。
    """
    import asyncio
    from src.open_llm_vtuber.llm_config_route import _load_conf, _is_configured_for_conf

    conf = tmp_path / "conf.yaml"
    conf.write_text(
        "character_config:\n"
        "  agent_config:\n"
        "    agent_settings:\n"
        "      basic_memory_agent:\n"
        "        llm_provider: 'lmstudio_llm'\n"
        "    llm_configs:\n"
        "      openai_compatible_llm:\n"
        "        base_url: 'https://api.openai.com/v1'\n"
        "        model: 'gpt-4o'\n"
        "        llm_api_key: 'your api key here'\n"
        "      lmstudio_llm:\n"
        "        base_url: 'http://localhost:1234/v1'\n"
        "        model: 'qwen/qwen2.5-vl-7b'\n"
        "        llm_api_key: 'lmstudio'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    data = _load_conf()
    assert asyncio.run(_is_configured_for_conf(data)) is True, (
        "llm_provider 指向 lmstudio_llm 時應視為已設定，"
        "不該因為 openai 區塊是佔位符而要求跑精靈"
    )


def test_empty_llm_provider_falls_through_to_block_check(tmp_path, monkeypatch):
    """空字串的 llm_provider 不是「使用者選了別的供應商」，是設定不完整。

    agent_factory.py 對空/缺值的 llm_provider 會直接 raise（開機失敗），所以
    這種情況必須落回既有的 openai 區塊判斷，不能被誤判成「已設定」而讓精靈
    永遠不出現——那樣使用者會卡在一個開不了機、也看不到設定畫面的狀態。
    """
    import asyncio
    from src.open_llm_vtuber.llm_config_route import _load_conf, _is_configured_for_conf

    conf = tmp_path / "conf.yaml"
    conf.write_text(
        "character_config:\n"
        "  agent_config:\n"
        "    agent_settings:\n"
        "      basic_memory_agent:\n"
        "        llm_provider: ''\n"
        "    llm_configs:\n"
        "      openai_compatible_llm:\n"
        "        base_url: 'https://api.openai.com/v1'\n"
        "        model: 'gpt-4o'\n"
        "        llm_api_key: 'your api key here'\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    data = _load_conf()
    assert asyncio.run(_is_configured_for_conf(data)) is False, (
        "llm_provider 是空字串時 agent 開機會直接失敗，"
        "不能因為短路邏輯就回報「已設定」"
    )


def test_resolve_base_url_default_fills_in_when_field_omitted():
    """apikey/ollama 模式故意不送 base_url（buildSavePayload 省略該欄位），
    body.get("base_url") 因此是 None——這種「欄位根本沒送」的情況必須拿到該
    provider 的預設 base_url，否則會被 "Missing base_url." 擋下。"""
    from src.open_llm_vtuber.llm_config_route import (
        _resolve_base_url_default,
        PROVIDER_DEFAULT_BASE_URL,
    )

    assert _resolve_base_url_default("openai", None) == PROVIDER_DEFAULT_BASE_URL["openai"]
    assert _resolve_base_url_default("ollama", None) == PROVIDER_DEFAULT_BASE_URL["ollama"]


def test_resolve_base_url_default_leaves_explicit_empty_string_alone():
    """custom 模式一定會送 base_url 欄位（即使使用者留白，值是 ''）。若把
    '' 跟「欄位沒送」用同一條 truthiness 規則處理，'' 會被悄悄換成 openai 的
    預設值，讓 'Missing base_url.' 永遠不會觸發——使用者會在完全沒填 URL 的
    情況下，被拿去打 api.openai.com 並得到一個文不對題的「金鑰被拒絕」錯誤。
    這裡驗證明確的空字串必須原封不動地穿透回去，讓呼叫端的 'if not base_url'
    檢查抓到它。"""
    from src.open_llm_vtuber.llm_config_route import _resolve_base_url_default

    assert _resolve_base_url_default("openai", "") == ""
    assert not _resolve_base_url_default("openai", "")
