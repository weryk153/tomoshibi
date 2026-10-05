"""
This module contains the pydantic model for the configurations of
different types of agents.
"""

from collections.abc import Mapping
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Any, Dict, ClassVar, Optional, Literal, List
from .i18n import I18nMixin, Description
from .stateless_llm import StatelessLLMConfigs

# ======== Configurations for different Agents ========


class ConversationConfig(I18nMixin, BaseModel):
    """對話用的模型與工具：引擎 agent 講話用哪一組 llm_configs、要不要開 MCP 工具、
    斷句方式。這個區塊以前叫 basic_memory_agent（那個 agent 已經拿掉）。"""

    llm_provider: Literal[
        "stateless_llm_with_template",
        "openai_compatible_llm",
        "claude_llm",
        "llama_cpp_llm",
        "ollama_llm",
        "lmstudio_llm",
        "openai_llm",
        "gemini_llm",
        "zhipu_llm",
        "deepseek_llm",
        "groq_llm",
        "mistral_llm",
    ] = Field(..., alias="llm_provider")

    faster_first_response: Optional[bool] = Field(True, alias="faster_first_response")
    segment_method: Literal["regex", "pysbd"] = Field("pysbd", alias="segment_method")
    use_mcpp: Optional[bool] = Field(False, alias="use_mcpp")
    mcp_enabled_servers: Optional[List[str]] = Field([], alias="mcp_enabled_servers")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "llm_provider": Description(
            en="Which llm_configs entry the conversation uses",
            zh="對話使用的語言模型（llm_configs 裡的哪一組）",
        ),
        "faster_first_response": Description(
            en="Whether to respond as soon as encountering a comma in the first sentence to reduce latency (default: True)",
            zh="是否在第一句回应时遇上逗号就直接生成音频以减少首句延迟（默认：True）",
        ),
        "segment_method": Description(
            en="Method for segmenting sentences: 'regex' or 'pysbd' (default: 'pysbd')",
            zh="分割句子的方法：'regex' 或 'pysbd'（默认：'pysbd'）",
        ),
        "use_mcpp": Description(
            en="Whether to use MCP (Model Context Protocol) for the agent (default: True)",
            zh="是否使用为智能体启用 MCP (Model Context Protocol) Plus（默认：False）",
        ),
        "mcp_enabled_servers": Description(
            en="List of MCP servers to enable for the agent",
            zh="为智能体启用 MCP 服务器列表",
        ),
    }


# =================================


class HumeAIConfig(I18nMixin, BaseModel):
    """Configuration for the Hume AI agent."""

    api_key: str = Field(..., alias="api_key")
    host: str = Field("api.hume.ai", alias="host")
    config_id: Optional[str] = Field(None, alias="config_id")
    idle_timeout: int = Field(15, alias="idle_timeout")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "api_key": Description(
            en="API key for Hume AI service", zh="Hume AI 服务的 API 密钥"
        ),
        "host": Description(
            en="Host URL for Hume AI service (default: api.hume.ai)",
            zh="Hume AI 服务的主机地址（默认：api.hume.ai）",
        ),
        "config_id": Description(
            en="Configuration ID for EVI settings", zh="EVI 配置 ID"
        ),
        "idle_timeout": Description(
            en="Idle timeout in seconds before disconnecting (default: 15)",
            zh="空闲超时断开连接的秒数（默认：15）",
        ),
    }


# =================================


class LettaConfig(I18nMixin, BaseModel):
    """Configuration for the Letta agent."""

    host: str = Field("localhost", alias="host")
    port: int = Field(8283, alias="port")
    id: str = Field(..., alias="id")
    faster_first_response: Optional[bool] = Field(True, alias="faster_first_response")
    segment_method: Literal["regex", "pysbd"] = Field("pysbd", alias="segment_method")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "host": Description(
            en="Host address for the Letta server", zh="Letta服务器的主机地址"
        ),
        "port": Description(
            en="Port number for the Letta server (default: 8283)",
            zh="Letta服务器的端口号（默认：8283）",
        ),
        "id": Description(
            en="Agent instance ID running on the Letta server",
            zh="指定Letta服务器上运行的Agent实例id",
        ),
    }


class CharacterEngineAgentConfig(I18nMixin, BaseModel):
    """character_engine_agent 的認知節奏。

    對話的設定（llm_provider、use_mcpp…）在 conversation 區塊，這裡只放
    引擎背景工作的部分。預設值跟引擎的 CompanionSettings 一致；character_engine/
    factory.py 把這份傳過去（timeout_seconds、max_rebase_turns 在那裡換成引擎的
    名字）。
    """

    emotion_every: int = Field(1, alias="emotion_every", ge=0)
    memory_every: int = Field(2, alias="memory_every", ge=0)
    self_memory_every: int = Field(2, alias="self_memory_every", ge=0)
    # 她自己的心情（引擎 CompanionSettings.mood_every）；空檔的臉跟著它。
    mood_every: int = Field(2, alias="mood_every", ge=0)
    summary_every: int = Field(0, alias="summary_every", ge=0)
    reflection_every: int = Field(6, alias="reflection_every", ge=0)
    goal_every: int = Field(4, alias="goal_every", ge=0)
    timeout_seconds: float = Field(60.0, alias="timeout_seconds", gt=0)
    max_rebase_turns: int = Field(3, alias="max_rebase_turns", ge=0)
    goal_max_age_days: int = Field(7, alias="goal_max_age_days", ge=0)
    goals_shown: int = Field(3, alias="goals_shown", ge=0)
    thoughts_shown: int = Field(2, alias="thoughts_shown", ge=0)
    foreground_patience_seconds: float = Field(
        120.0, alias="foreground_patience_seconds", gt=0
    )
    max_history_messages: int = Field(80, alias="max_history_messages", ge=0)
    # 背景工作另外用的端點與模型；兩個都有才用（character_engine/factory.py）。
    background_base_url: str = Field("", alias="background_base_url")
    background_model: str = Field("", alias="background_model")
    background_api_key: str = Field("", alias="background_api_key")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "max_history_messages": Description(
            en="How many messages of the conversation are kept for the model",
            zh="對話最多留幾則給模型",
        ),
        "emotion_every": Description(
            en="Analyse the user's emotion every N turns (0 disables)",
            zh="每幾輪分析一次對方的情緒（0 為停用）",
        ),
        "memory_every": Description(
            en="Extract engine memories every N turns (0 disables)",
            zh="每幾輪擷取一次引擎記憶（0 為停用）",
        ),
        "self_memory_every": Description(
            en="Remember what she said about herself every N turns (0 disables)",
            zh="每幾輪記一次她自己說過的事（0 為停用）",
        ),
        "mood_every": Description(
            en="Update her own mood every N turns; her resting face follows it (0 disables)",
            zh="每幾輪更新一次她自己的心情，空檔的表情跟著它（0 為停用）",
        ),
        "background_base_url": Description(
            en="Another endpoint for the background jobs (empty: the one she talks with)",
            zh="背景工作另外用的端點（空著就跟她講話用同一個）",
        ),
        "background_model": Description(
            en="The model at that endpoint (both must be set to be used)",
            zh="那個端點的模型（兩個都填才會用）",
        ),
        "background_api_key": Description(
            en="API key for that endpoint (empty: the one she talks with)",
            zh="那個端點的 API 金鑰（空著就沿用她講話那一個）",
        ),
        "summary_every": Description(
            en="Summarise the conversation every N turns (0 disables)",
            zh="每幾輪摘要一次對話（0 為停用）",
        ),
        "reflection_every": Description(
            en="Let the character reflect every N turns (0 disables)",
            zh="每幾輪讓角色反思一次（0 為停用）",
        ),
        "goal_every": Description(
            en="Let the character form goals every N turns (0 disables)",
            zh="每幾輪讓角色產生一次目標（0 為停用）",
        ),
        "timeout_seconds": Description(
            en="Timeout for each background worker call",
            zh="每個背景工作的逾時秒數",
        ),
        "max_rebase_turns": Description(
            en="A background result this many turns late is still used",
            zh="背景結果落後幾輪以內仍然採用",
        ),
        "foreground_patience_seconds": Description(
            en="Background work resumes after this long without an end-of-reply signal",
            zh="對話沒回報講完時，背景工作等多久之後恢復",
        ),
        "goal_max_age_days": Description(
            en="Goals not updated for this many days leave the prompt",
            zh="超過幾天沒更新的目標不再寫進提示",
        ),
        "goals_shown": Description(
            en="How many goals (the most pressing) she keeps in mind",
            zh="她同時放在心上的目標最多幾條（最急的優先）",
        ),
        "thoughts_shown": Description(
            en="How many thoughts (the newest) she keeps in mind",
            zh="她同時放在心上的想法最多幾條（最新的優先）",
        ),
    }


def conversation_block(agent_settings: Mapping | None) -> dict:
    """原始 YAML 字典裡對話用的設定區塊：新名字 conversation，舊名字 basic_memory_agent。

    給不經過 pydantic、直接讀 conf.yaml 字典的人用（翻譯、語言模型頁、工具開關）。
    """
    if not isinstance(agent_settings, Mapping):
        return {}
    for key in ("conversation", "basic_memory_agent"):
        block = agent_settings.get(key)
        if isinstance(block, Mapping):
            return dict(block)
    return {}


def with_conversation_block(character_config: Mapping) -> dict:
    """角色檔深度合併到底稿之前，把舊名字 basic_memory_agent 改成 conversation。

    底稿 conf.yaml 開機時已經升級成 conversation；角色檔還寫舊名字的話，合併後兩個
    名字並存，pydantic 以 conversation（底稿的）為準，角色檔指定的模型就被蓋掉。
    兩個名字都在時一樣以 conversation 為準。
    """
    agent_config = character_config.get("agent_config")
    settings = (
        agent_config.get("agent_settings")
        if isinstance(agent_config, Mapping)
        else None
    )
    if not isinstance(settings, Mapping) or not isinstance(
        settings.get("basic_memory_agent"), Mapping
    ):
        return dict(character_config)
    settings = dict(settings)
    old = settings.pop("basic_memory_agent")
    new = settings.get("conversation")
    settings["conversation"] = {**old, **new} if isinstance(new, Mapping) else dict(old)
    return {
        **character_config,
        "agent_config": {**agent_config, "agent_settings": settings},
    }


class AgentSettings(I18nMixin, BaseModel):
    """Settings for the conversation and the agents."""

    conversation: Optional[ConversationConfig] = Field(None, alias="conversation")
    hume_ai_agent: Optional[HumeAIConfig] = Field(None, alias="hume_ai_agent")
    letta_agent: Optional[LettaConfig] = Field(None, alias="letta_agent")
    character_engine_agent: Optional[CharacterEngineAgentConfig] = Field(
        None, alias="character_engine_agent"
    )

    @model_validator(mode="before")
    @classmethod
    def _old_block_name(cls, data: Any) -> Any:
        # 舊 conf.yaml 與角色檔的深度合併只有 basic_memory_agent；新名字在就以新名字為準。
        if isinstance(data, Mapping) and "basic_memory_agent" in data:
            data = dict(data)
            old = data.pop("basic_memory_agent")
            data.setdefault("conversation", old)
        return data

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "conversation": Description(
            en="Model and tools for the conversation", zh="對話用的模型與工具"
        ),
        "character_engine_agent": Description(
            en="Cognition cadence for the AI Character Engine agent",
            zh="AI Character Engine 代理的認知節奏",
        ),
        "hume_ai_agent": Description(
            en="Configuration for Hume AI agent", zh="Hume AI 代理配置"
        ),
        "letta_agent": Description(
            en="Configuration for Letta agent", zh="Letta 代理配置"
        ),
    }


_RETIRED_CHOICES = {"basic_memory_agent", "mem0_agent"}


class AgentConfig(I18nMixin, BaseModel):
    """This class contains all of the configurations related to agent."""

    conversation_agent_choice: Literal[
        "character_engine_agent", "hume_ai_agent", "letta_agent"
    ] = Field("character_engine_agent", alias="conversation_agent_choice")
    agent_settings: AgentSettings = Field(..., alias="agent_settings")
    llm_configs: StatelessLLMConfigs = Field(..., alias="llm_configs")

    @field_validator("conversation_agent_choice", mode="before")
    @classmethod
    def _retired_choice(cls, value: Any) -> Any:
        # 舊 agent 拿掉了；mem0_agent 的程式本來就是空檔。兩者都改由引擎 agent 對話。
        return "character_engine_agent" if value in _RETIRED_CHOICES else value

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "conversation_agent_choice": Description(
            en="Type of conversation agent to use", zh="要使用的对话代理类型"
        ),
        "agent_settings": Description(
            en="Settings for different agent types", zh="不同代理类型的设置"
        ),
        "llm_configs": Description(
            en="Pool of LLM provider configurations", zh="语言模型提供者配置池"
        ),
        "faster_first_response": Description(
            en="Whether to respond as soon as encountering a comma in the first sentence to reduce latency (default: True)",
            zh="是否在第一句回应时遇上逗号就直接生成音频以减少首句延迟（默认：True）",
        ),
        "segment_method": Description(
            en="Method for segmenting sentences: 'regex' or 'pysbd' (default: 'pysbd')",
            zh="分割句子的方法：'regex' 或 'pysbd'（默认：'pysbd'）",
        ),
    }
