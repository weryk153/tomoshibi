"""引擎的背景模型：ASR 還原與翻譯審核另外問它一次。

character_engine_agent 的 background_base_url／background_model 都有才用；
金鑰沒另外給就借對話模型的。思考開關（REASONING_KEYS）照對話模型的設定帶。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .character_engine.factory import REASONING_KEYS


@dataclass
class ChatClient:
    """OpenAI 相容的 /chat/completions，一次一個請求、不串流。"""

    base_url: str
    model: str
    api_key: str = ""
    request_options: Optional[dict] = None
    # 呼叫端用 wait_for 管上限；這只是連線層的保險。
    timeout_seconds: float = 5.0

    async def complete(self, messages: list[dict]) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http:
            response = await http.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                json={
                    "model": self.model,
                    "messages": messages,
                    **(self.request_options or {}),
                },
                headers=headers,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"] or ""


def background_client(
    character: Any, *, max_tokens: int, timeout_seconds: float
) -> Optional[ChatClient]:
    """這個角色的背景模型；網址和模型都有才用，不然是 None。"""
    agent = getattr(character, "agent_config", None)
    settings = getattr(agent, "agent_settings", None)
    engine = getattr(settings, "character_engine_agent", None)
    base_url = str(getattr(engine, "background_base_url", "") or "").strip()
    model = str(getattr(engine, "background_model", "") or "").strip()
    if not base_url or not model:
        return None
    provider = getattr(getattr(settings, "conversation", None), "llm_provider", "")
    llm = getattr(getattr(agent, "llm_configs", None), str(provider or ""), None)
    extra_body = dict(getattr(llm, "extra_body", None) or {})
    return ChatClient(
        base_url=base_url,
        model=model,
        api_key=str(getattr(engine, "background_api_key", "") or "")
        or str(getattr(llm, "llm_api_key", "") or ""),
        request_options={
            "temperature": 0,
            "max_tokens": max_tokens,
            **{k: v for k, v in extra_body.items() if k in REASONING_KEYS},
        },
        timeout_seconds=timeout_seconds,
    )
