"""她回不了話時，把模型那邊的錯誤翻成使用者看得懂、知道怎麼修的一句話。

引擎丟上來的是 HostBridgeError("Character processing failed. Check the configured
providers.")，原因一層層接在 __cause__ 上（LLMError ← openai／httpx 的錯誤）。新使用者
只看到那句英文，不會知道是 Ollama 沒開、網址打錯、模型沒下載還是金鑰不對。這裡往回
找原因，認得出來的回傳翻譯鍵、參數與預設文字；認不出來的回 None，照舊顯示原文。
"""

from __future__ import annotations

from typing import Any, Optional

PROVIDER_NAMES = {
    "ollama_llm": "Ollama",
    "lmstudio_llm": "LM Studio",
    "openai_compatible_llm": "OpenAI-compatible",
    "openai_llm": "OpenAI",
    "gemini_llm": "Gemini",
    "deepseek_llm": "DeepSeek",
    "groq_llm": "Groq",
    "mistral_llm": "Mistral",
    "zhipu_llm": "Zhipu",
    "llama_cpp_llm": "llama.cpp",
}

MESSAGES = {
    "errors.llmUnreachable": "連不到語言模型（{provider}，{url}）。請確認它有開著，或到「設定 › 模型」換一個。",
    "errors.llmModelMissing": "語言模型 {provider} 找不到模型「{model}」。請到「設定 › 模型」選一個已經下載的模型。",
    "errors.llmAuth": "語言模型 {provider} 拒絕連線：API 金鑰不對或沒填。請到「設定 › 模型」檢查。",
    "errors.llmTimeout": "語言模型 {provider} 太久沒回應，可能還在載入模型。稍等一下再試。",
}


def _causes(error: BaseException):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        yield error
        error = error.__cause__ or error.__context__


def _kind(error: BaseException) -> Optional[str]:
    for cause in _causes(error):
        name = type(cause).__name__
        text = str(cause).lower()
        if name in (
            "APITimeoutError",
            "ReadTimeout",
            "ConnectTimeout",
            "TimeoutException",
        ):
            return "errors.llmTimeout"
        if name in ("AuthenticationError", "PermissionDeniedError"):
            return "errors.llmAuth"
        if name == "NotFoundError" or ("model" in text and "not found" in text):
            return "errors.llmModelMissing"
        if name in ("APIConnectionError", "ConnectError", "ConnectionRefusedError") or (
            name == "OSError" and "connection" in text
        ):
            return "errors.llmUnreachable"
    return None


def describe_llm_failure(
    error: BaseException, *, provider: str, base_url: str, model: str
) -> Optional[dict[str, Any]]:
    """{"text_key", "params", "message"}；認不出原因是 None。"""
    key = _kind(error)
    if key is None:
        return None
    params = {
        "provider": PROVIDER_NAMES.get(provider, provider or "?"),
        "url": base_url or "?",
        "model": model or "?",
    }
    return {
        "text_key": key,
        "params": params,
        "message": MESSAGES[key].format(**params),
    }


def llm_settings_of(context: Any) -> dict[str, str]:
    """這個連線正在用的模型來源：provider、base_url、model。讀不到的留空。"""
    try:
        agent = context.character_config.agent_config
        provider = str(agent.agent_settings.conversation.llm_provider or "")
        llm = getattr(agent.llm_configs, provider, None)
        return {
            "provider": provider,
            "base_url": str(getattr(llm, "base_url", "") or ""),
            "model": str(getattr(llm, "model", "") or ""),
        }
    except Exception:  # noqa: BLE001 — 讀不到就不寫出來
        return {"provider": "", "base_url": "", "model": ""}
