from typing import Type, Literal
from loguru import logger

from .agents.agent_interface import AgentInterface
from .agents.basic_memory_agent import BasicMemoryAgent
from .stateless_llm_factory import LLMFactory as StatelessLLMFactory
# NOTE: hume_ai / letta_agent are imported LAZILY inside their branches below.
# Importing them at module top pulls their (optional, possibly unbundled) deps on
# every startup, so a missing dep would crash the whole app even for users who
# never pick those agents. Keep the default (basic_memory_agent) path import-clean.

from ..mcpp.tool_manager import ToolManager
from ..mcpp.tool_executor import ToolExecutor
from typing import Optional


def _engine_settings(settings: dict, *, long_term_memory: bool) -> dict:
    """記憶頁關掉長期記憶時，引擎也不再抽記憶、不再把記憶帶進對話。"""
    if long_term_memory:
        return dict(settings)
    return {
        **settings,
        "memory_every": 0,
        "memories_recalled": 0,
        "self_memory_every": 0,
        # 以前記過的也不再帶進對話：關掉之前，主機那一套兩份記憶都不注入。
        "self_memories_shown": 0,
    }


class AgentFactory:
    @staticmethod
    def create_agent(
        conversation_agent_choice: str,
        agent_settings: dict,
        llm_configs: dict,
        system_prompt: str,
        live2d_model=None,
        tts_preprocessor_config=None,
        **kwargs,
    ) -> Type[AgentInterface]:
        """Create an agent based on the configuration.

        Args:
            conversation_agent_choice: The type of agent to create
            agent_settings: Settings for different types of agents
            llm_configs: Pool of LLM configurations
            system_prompt: The system prompt to use
            live2d_model: Live2D model instance for expression extraction
            tts_preprocessor_config: Configuration for TTS preprocessing
            **kwargs: Additional arguments
        """
        logger.info(f"Initializing agent: {conversation_agent_choice}")

        if conversation_agent_choice in (
            "basic_memory_agent",
            "character_engine_agent",
        ):
            # character_engine_agent 是「BasicMemoryAgent 加上引擎的認知」，前景的
            # 設定與它完全相同，所以共用 basic_memory_agent 這個設定區塊——設定頁、
            # MCP、記憶整理、翻譯都讀那個區塊，另開一份的話它們全部要跟著改。
            # Get the LLM provider choice from agent settings
            basic_memory_settings: dict = agent_settings.get("conversation") or {}
            llm_provider: str = basic_memory_settings.get("llm_provider")

            if not llm_provider:
                raise ValueError("LLM provider not specified for basic memory agent")

            # Get the LLM config for this provider
            llm_config: dict = llm_configs.get(llm_provider)
            interrupt_method: Literal["system", "user"] = llm_config.pop(
                "interrupt_method", "user"
            )

            if not llm_config:
                raise ValueError(
                    f"Configuration not found for LLM provider: {llm_provider}"
                )

            # Create the stateless LLM
            llm = StatelessLLMFactory.create_llm(
                llm_provider=llm_provider, system_prompt=system_prompt, **llm_config
            )

            tool_prompts = kwargs.get("system_config", {}).get("tool_prompts", {})

            # Extract MCP components/data needed by BasicMemoryAgent from kwargs
            tool_manager: Optional[ToolManager] = kwargs.get("tool_manager")
            tool_executor: Optional[ToolExecutor] = kwargs.get("tool_executor")
            mcp_prompt_string: str = kwargs.get("mcp_prompt_string", "")

            # Create the agent with the LLM and live2d_model
            basic = dict(
                llm=llm,
                system=system_prompt,
                live2d_model=live2d_model,
                tts_preprocessor_config=tts_preprocessor_config,
                faster_first_response=basic_memory_settings.get(
                    "faster_first_response", True
                ),
                segment_method=basic_memory_settings.get("segment_method", "pysbd"),
                use_mcpp=basic_memory_settings.get("use_mcpp", False),
                interrupt_method=interrupt_method,
                tool_prompts=tool_prompts,
                tool_manager=tool_manager,
                tool_executor=tool_executor,
                mcp_prompt_string=mcp_prompt_string,
                # 記憶的字形正規化要用跟顯示／歷史同一個語言設定，否則三條路
                # 會各存各的（見 BasicMemoryAgent._add_message 的說明）。
                player_language=str(
                    kwargs.get("output_language")
                    or kwargs.get("system_config", {}).get("player_language", "")
                    or ""
                ),
                # 短期記憶的截斷預算要知道推論端載了多大的 window，而那個值
                # 只問得到、設定裡沒有（見 context_window 模組）。
                llm_base_url=str(llm_config.get("base_url") or ""),
                llm_model=str(llm_config.get("model") or ""),
            )
            if conversation_agent_choice == "basic_memory_agent":
                return BasicMemoryAgent(**basic)

            # 引擎是選用的（要 Python 3.11 以上），跟 hume_ai／letta 一樣延遲匯入。
            # 先建引擎那一側：沒裝引擎的話，這裡會丟出寫明做法的錯誤。
            from ..character_engine.factory import build_companion, current_companion

            conf_uid = str(kwargs.get("conf_uid") or "").strip()
            if not conf_uid:
                raise ValueError(
                    "character_engine_agent needs the character's conf_uid"
                )
            key = build_companion(
                conf_uid=conf_uid,
                character_name=str(kwargs.get("character_name") or ""),
                system=system_prompt,
                provider=llm_provider,
                llm_config=llm_config,
                settings=_engine_settings(
                    agent_settings.get("character_engine_agent") or {},
                    long_term_memory=kwargs.get("long_term_memory_enabled", True),
                ),
                language=basic["player_language"],
            )
            from .agents.character_engine_agent import CharacterEngineAgent

            return CharacterEngineAgent(
                # 給的是「怎麼查」而不是它本身：設定變了引擎那一側會換一個，
                # 而舊的 agent 還被別的連線拿著。
                companion=lambda: current_companion(key),
                conf_uid=conf_uid,
                character_name=str(kwargs.get("character_name") or ""),
                **basic,
            )

        elif conversation_agent_choice == "mem0_agent":
            from .agents.mem0_llm import LLM as Mem0LLM

            mem0_settings = agent_settings.get("mem0_agent", {})
            if not mem0_settings:
                raise ValueError("Mem0 agent settings not found")

            # Validate required settings
            required_fields = ["base_url", "model", "mem0_config"]
            for field in required_fields:
                if field not in mem0_settings:
                    raise ValueError(
                        f"Missing required field '{field}' in mem0_agent settings"
                    )

            return Mem0LLM(
                user_id=kwargs.get("user_id", "default"),
                system=system_prompt,
                live2d_model=live2d_model,
                **mem0_settings,
            )

        elif conversation_agent_choice == "hume_ai_agent":
            from .agents.hume_ai import HumeAIAgent

            settings = agent_settings.get("hume_ai_agent", {})
            return HumeAIAgent(
                api_key=settings.get("api_key"),
                host=settings.get("host", "api.hume.ai"),
                config_id=settings.get("config_id"),
                idle_timeout=settings.get("idle_timeout", 15),
            )

        elif conversation_agent_choice == "letta_agent":
            from .agents.letta_agent import LettaAgent

            settings = agent_settings.get("letta_agent", {})
            return LettaAgent(
                live2d_model=live2d_model,
                id=settings.get("id"),
                tts_preprocessor_config=tts_preprocessor_config,
                faster_first_response=settings.get("faster_first_response"),
                segment_method=settings.get("segment_method"),
                host=settings.get("host"),
                port=settings.get("port"),
            )

        else:
            raise ValueError(f"Unsupported agent type: {conversation_agent_choice}")
