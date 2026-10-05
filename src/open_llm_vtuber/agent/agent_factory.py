from typing import Type

from loguru import logger

from .agents.agent_interface import AgentInterface

# 只剩 AI Character Engine 驅動對話。hume_ai / letta_agent 在各自的分支裡才匯入：
# 它們的相依是選用的，放在檔頭的話少裝一個就整個 app 起不來。


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
        """Create the conversation agent from the configuration."""
        logger.info(f"Initializing agent: {conversation_agent_choice}")

        if conversation_agent_choice == "character_engine_agent":
            conversation: dict = agent_settings.get("conversation") or {}
            llm_provider: str = conversation.get("llm_provider")
            if not llm_provider:
                raise ValueError(
                    "llm_provider is not set in agent_settings.conversation"
                )
            llm_config: dict = dict(llm_configs.get(llm_provider) or {})
            if not llm_config:
                raise ValueError(
                    f"Configuration not found for LLM provider: {llm_provider}"
                )
            # 舊 agent 才用得到的鍵；留著的話引擎那一側會把它當成模型參數。
            llm_config.pop("interrupt_method", None)

            from ..character_engine.factory import build_companion, current_companion

            conf_uid = str(kwargs.get("conf_uid") or "").strip()
            if not conf_uid:
                raise ValueError(
                    "character_engine_agent needs the character's conf_uid"
                )
            player_language = str(
                kwargs.get("output_language")
                or kwargs.get("system_config", {}).get("player_language", "")
                or ""
            )
            # 她的人設原文，逐字包在 system_prompt 裡面；給引擎的 CharacterProfile.
            # background 讀，背景工作（情緒、心情…）才拿得到人設摘要。
            persona = str(kwargs.get("persona_prompt") or "")
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
                language=player_language,
                persona=persona,
            )
            from .agents.character_engine_agent import CharacterEngineAgent

            return CharacterEngineAgent(
                # 給的是「怎麼查」而不是它本身：設定變了引擎那一側會換一個，
                # 而舊的 agent 還被別的連線拿著。
                companion=lambda: current_companion(key),
                conf_uid=conf_uid,
                character_name=str(kwargs.get("character_name") or ""),
                system=system_prompt,
                persona=persona,
                mood_key=key,
                live2d_model=live2d_model,
                tts_preprocessor_config=tts_preprocessor_config,
                faster_first_response=conversation.get("faster_first_response", True),
                segment_method=conversation.get("segment_method", "pysbd"),
                use_mcpp=bool(conversation.get("use_mcpp", False)),
                tool_manager=kwargs.get("tool_manager"),
                tool_executor=kwargs.get("tool_executor"),
                player_language=player_language,
            )

        if conversation_agent_choice == "hume_ai_agent":
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
