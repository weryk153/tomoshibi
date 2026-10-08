import os
import json
from typing import Callable
from loguru import logger
from .character_mood import follow_mood, send_character_mood
from fastapi import WebSocket

from prompts import prompt_loader
from .avatar_model import AvatarModel
from .asr.asr_interface import ASRInterface
from .tts.tts_interface import TTSInterface
from .vad.vad_interface import VADInterface
from .agent.agents.agent_interface import AgentInterface
from .translate.translate_interface import TranslateInterface

from .mcpp.server_registry import ServerRegistry
from .mcpp.tool_manager import ToolManager
from .mcpp.mcp_client import MCPClient
from .mcpp.tool_executor import ToolExecutor
from .mcpp.tool_adapter import ToolAdapter

from .asr.asr_factory import ASRFactory
from .tts.tts_factory import TTSFactory
from .vad.vad_factory import VADFactory
from .agent.agent_factory import AgentFactory
from .translate.translate_factory import TranslateFactory

from .config_manager import (
    Config,
    AgentConfig,
    CharacterConfig,
    SystemConfig,
    ASRConfig,
    TTSConfig,
    VADConfig,
    TranslatorConfig,
    read_yaml,
    validate_config,
    with_conversation_block,
)


class ServiceContext:
    """Initializes, stores, and updates the asr, tts, and llm instances and other
    configurations for a connected client."""

    def __init__(self):
        self.config: Config = None
        self.system_config: SystemConfig = None
        self.character_config: CharacterConfig = None

        self.live2d_model: AvatarModel = None
        self.asr_engine: ASRInterface = None
        self.tts_engine: TTSInterface = None
        self.agent_engine: AgentInterface = None
        # translate_engine can be none if translation is disabled
        self.vad_engine: VADInterface | None = None
        self.translate_engine: TranslateInterface | None = None
        # Voice language (V) the current audio translate_engine was built to target.
        # Tracked so the audio engine is rebuilt when V changes on a character switch
        # even if the translator_config block itself is unchanged.
        self._audio_translate_voice_lang: str | None = None
        # 引擎建立時帶的角色名單（專有名詞、口頭禪）；換角色時名單不同就重建。
        self._audio_translate_terms: tuple[dict, dict] | None = None
        self._subtitle_terms: tuple[dict, dict] | None = None
        # display-only subtitle translation engine; None when disabled
        self.subtitle_translate_engine: TranslateInterface | None = None

        self.mcp_server_registery: ServerRegistry | None = None
        self.tool_adapter: ToolAdapter | None = None
        self.tool_manager: ToolManager | None = None
        self.mcp_client: MCPClient | None = None
        self.tool_executor: ToolExecutor | None = None

        # the system prompt is a combination of the persona prompt and live2d expression prompt
        self.system_prompt: str = None
        # The character's own prompt is kept separately from an applied persona
        # preset, so "use character default" can restore it without reading or
        # rewriting the character YAML.
        self.character_persona_prompt: str = ""
        self.active_persona_id: str | None = None
        # Filename of the character override represented by this context.  The
        # display name/UID are not sufficient because users may reuse them.
        self.active_config_file: str = "conf.yaml"
        self.stage_director_prompt: str = ""

        # Store the generated MCP prompt string (if MCP enabled)
        self.mcp_prompt: str = ""

        self.history_uid: str = ""  # Add history_uid field

        self.send_text: Callable = None
        self.client_uid: str = None

        # 停止把她的心情送給這個頁面（見 _follow_mood）。
        self._stop_following_mood: Callable | None = None

    def __str__(self):
        return (
            f"ServiceContext:\n"
            f"  System Config: {'Loaded' if self.system_config else 'Not Loaded'}\n"
            f"    Details: {json.dumps(self.system_config.model_dump(), indent=6) if self.system_config else 'None'}\n"
            f"  Live2D Model: {self.live2d_model.model_info if self.live2d_model else 'Not Loaded'}\n"
            f"  ASR Engine: {type(self.asr_engine).__name__ if self.asr_engine else 'Not Loaded'}\n"
            f"    Config: {json.dumps(self.character_config.asr_config.model_dump(), indent=6) if self.character_config.asr_config else 'None'}\n"
            f"  TTS Engine: {type(self.tts_engine).__name__ if self.tts_engine else 'Not Loaded'}\n"
            f"    Config: {json.dumps(self.character_config.tts_config.model_dump(), indent=6) if self.character_config.tts_config else 'None'}\n"
            f"  LLM Engine: {type(self.agent_engine).__name__ if self.agent_engine else 'Not Loaded'}\n"
            f"    Agent Config: {json.dumps(self.character_config.agent_config.model_dump(), indent=6) if self.character_config.agent_config else 'None'}\n"
            f"  VAD Engine: {type(self.vad_engine).__name__ if self.vad_engine else 'Not Loaded'}\n"
            f"    Agent Config: {json.dumps(self.character_config.vad_config.model_dump(), indent=6) if self.character_config.vad_config else 'None'}\n"
            f"  System Prompt: {self.system_prompt or 'Not Set'}\n"
            f"  MCP Enabled: {'Yes' if self.mcp_client else 'No'}"
        )

    # ==== Initializers

    async def _init_mcp_components(self, use_mcpp, enabled_servers):
        """Initializes MCP components based on configuration, dynamically fetching tool info."""
        logger.debug(
            f"Initializing MCP components: use_mcpp={use_mcpp}, enabled_servers={enabled_servers}"
        )

        # Reset MCP components first
        self.mcp_server_registery = None
        self.tool_manager = None
        self.mcp_client = None
        self.tool_executor = None
        self.json_detector = None
        self.mcp_prompt = ""

        if use_mcpp and enabled_servers:
            # 1. Initialize ServerRegistry
            self.mcp_server_registery = ServerRegistry()
            logger.info("ServerRegistry initialized or referenced.")

            # 2. Use ToolAdapter to get the MCP prompt and tools
            if not self.tool_adapter:
                logger.error(
                    "ToolAdapter not initialized before calling _init_mcp_components."
                )
                self.mcp_prompt = "[Error: ToolAdapter not initialized]"
                return  # Exit if ToolAdapter is mandatory and not initialized

            try:
                (
                    mcp_prompt_string,
                    openai_tools,
                    claude_tools,
                ) = await self.tool_adapter.get_tools(enabled_servers)
                # Store the generated prompt string
                self.mcp_prompt = mcp_prompt_string
                logger.info(
                    f"Dynamically generated MCP prompt string (length: {len(self.mcp_prompt)})."
                )
                logger.info(
                    f"Dynamically formatted tools - OpenAI: {len(openai_tools)}, Claude: {len(claude_tools)}."
                )

                # 3. Initialize ToolManager with the fetched formatted tools

                _, raw_tools_dict = await self.tool_adapter.get_server_and_tool_info(
                    enabled_servers
                )
                self.tool_manager = ToolManager(
                    formatted_tools_openai=openai_tools,
                    formatted_tools_claude=claude_tools,
                    initial_tools_dict=raw_tools_dict,
                )
                logger.info("ToolManager initialized with dynamically fetched tools.")

            except Exception as e:
                logger.error(
                    f"Failed during dynamic MCP tool construction: {e}", exc_info=True
                )
                # Ensure dependent components are not created if construction fails
                self.tool_manager = None
                self.mcp_prompt = "[Error constructing MCP tools/prompt]"

            # 4. Initialize MCPClient
            if self.mcp_server_registery:
                self.mcp_client = MCPClient(
                    self.mcp_server_registery, self.send_text, self.client_uid
                )
                logger.info("MCPClient initialized for this session.")
            else:
                logger.error(
                    "MCP enabled but ServerRegistry not available. MCPClient not created."
                )
                self.mcp_client = None  # Ensure it's None

            # 5. Initialize ToolExecutor
            if self.mcp_client and self.tool_manager:
                self.tool_executor = ToolExecutor(self.mcp_client, self.tool_manager)
                logger.info("ToolExecutor initialized for this session.")
            else:
                logger.warning(
                    "MCPClient or ToolManager not available. ToolExecutor not created."
                )
                self.tool_executor = None  # Ensure it's None

            logger.info("StreamJSONDetector initialized for this session.")

        elif use_mcpp and not enabled_servers:
            logger.warning(
                "use_mcpp is True, but mcp_enabled_servers list is empty. MCP components not initialized."
            )
        else:
            logger.debug(
                "MCP components not initialized (use_mcpp is False or no enabled servers)."
            )

    async def close(self):
        """Clean up resources, especially the MCPClient."""
        logger.info("Closing ServiceContext resources...")
        self._unfollow_mood()
        if self.mcp_client:
            logger.info(f"Closing MCPClient for context instance {id(self)}...")
            await self.mcp_client.aclose()
            self.mcp_client = None
        if self.agent_engine and hasattr(self.agent_engine, "close"):
            await self.agent_engine.close()  # Ensure agent resources are also closed
        logger.info("ServiceContext closed.")

    def _unfollow_mood(self) -> None:
        """停止把她的心情送給這個頁面，如果正在跟著的話。_follow_mood 換到新的
        agent 之前、close() 整個收掉之前都要做，寫一次兩邊共用。"""
        stop = getattr(self, "_stop_following_mood", None)
        if stop is not None:
            stop()
            self._stop_following_mood = None

    def _follow_mood(self) -> None:
        """背景結果改了她的心情時送給這個頁面。agent 換了（換角色、存設定）就
        改跟新的那一個；舊的停掉，不然換走的角色還會送心情過來。"""
        self._unfollow_mood()
        self._stop_following_mood = follow_mood(
            self.agent_engine, getattr(self, "send_text", None)
        )

    async def load_cache(
        self,
        config: Config,
        system_config: SystemConfig,
        character_config: CharacterConfig,
        live2d_model: AvatarModel,
        asr_engine: ASRInterface,
        tts_engine: TTSInterface,
        vad_engine: VADInterface,
        agent_engine: AgentInterface,
        translate_engine: TranslateInterface | None,
        mcp_server_registery: ServerRegistry | None = None,
        tool_adapter: ToolAdapter | None = None,
        send_text: Callable = None,
        client_uid: str = None,
        subtitle_translate_engine: TranslateInterface | None = None,
        character_persona_prompt: str | None = None,
        active_persona_id: str | None = None,
        active_config_file: str = "conf.yaml",
    ) -> None:
        """
        Load the ServiceContext with the reference of the provided instances.
        Pass by reference so no reinitialization will be done.
        """
        if not character_config:
            raise ValueError("character_config cannot be None")
        if not system_config:
            raise ValueError("system_config cannot be None")

        self.config = config
        self.system_config = system_config
        self.character_config = character_config
        self.character_persona_prompt = (
            character_persona_prompt
            if character_persona_prompt is not None
            else character_config.persona_prompt
        )
        self.active_persona_id = active_persona_id
        self.active_config_file = active_config_file
        self.live2d_model = live2d_model
        self.asr_engine = asr_engine
        self.tts_engine = tts_engine
        self.vad_engine = vad_engine
        self.agent_engine = agent_engine
        self.translate_engine = translate_engine
        # Unknown which V a cached engine was built for; force a rebuild on the next
        # load_from_config so the audio target matches the active character's V.
        self._audio_translate_voice_lang = None
        self.subtitle_translate_engine = subtitle_translate_engine
        # Load potentially shared components by reference
        self.mcp_server_registery = mcp_server_registery
        self.tool_adapter = tool_adapter
        self.send_text = send_text
        self.client_uid = client_uid

        # Initialize session-specific MCP components
        await self._init_mcp_components(
            self.character_config.agent_config.agent_settings.conversation.use_mcpp,
            self.character_config.agent_config.agent_settings.conversation.mcp_enabled_servers,
        )
        # 這個頁面現在拿的是這個 agent。
        self._follow_mood()

        logger.debug(f"Loaded service context with cache: {character_config}")

    async def load_from_config(self, config: Config) -> None:
        """
        Load the ServiceContext with the config.
        Reinitialize the instances if the config is different.

        Parameters:
        - config (Dict): The configuration dictionary.
        """
        # Resolve the persona preset before initializing the agent. The original
        # character prompt remains available for reset, while only this in-memory
        # config copy receives the effective preset prompt.
        from .persona_store import resolve_active_persona

        character_persona_prompt = config.character_config.persona_prompt
        active_persona = resolve_active_persona(config.character_config.conf_uid)
        if active_persona:
            config = config.model_copy(deep=True)
            config.character_config.persona_prompt = active_persona["prompt"]
            self.active_persona_id = active_persona["id"]
        else:
            self.active_persona_id = None
        self.character_persona_prompt = character_persona_prompt

        if not self.config:
            self.config = config

        if not self.system_config:
            self.system_config = config.system_config

        if not self.character_config:
            self.character_config = config.character_config

        # update all sub-configs

        # init live2d from character config
        self.init_live2d(config.character_config.live2d_model_name)

        # init asr from character config
        self.init_asr(config.character_config.asr_config, config.character_config)

        # init tts from character config
        self.init_tts(config.character_config.tts_config)

        # init vad from character config
        self.init_vad(config.character_config.vad_config)

        # Initialize shared ToolAdapter if it doesn't exist yet
        if (
            not self.tool_adapter
            and config.character_config.agent_config.agent_settings.conversation.use_mcpp
        ):
            if not self.mcp_server_registery:
                logger.info(
                    "Initializing shared ServerRegistry within load_from_config."
                )
                self.mcp_server_registery = ServerRegistry()
            logger.info("Initializing shared ToolAdapter within load_from_config.")
            self.tool_adapter = ToolAdapter(server_registery=self.mcp_server_registery)

        # Initialize MCP Components before initializing Agent
        await self._init_mcp_components(
            config.character_config.agent_config.agent_settings.conversation.use_mcpp,
            config.character_config.agent_config.agent_settings.conversation.mcp_enabled_servers,
        )

        # init agent from character config
        await self.init_agent(
            config.character_config.agent_config,
            config.character_config.persona_prompt,
            character_config=config.character_config,
        )

        # Derive the NEW character's voice language V from the config being loaded
        # (self.character_config is still the OLD one here — it's assigned below).
        # The audio translate engine targets V so the spoken voice always matches the
        # character's voice language regardless of the reply (player) language.
        from .conversations.conversation_utils import derive_voice_lang

        self.init_translate(
            config.character_config.tts_preprocessor_config.translator_config,
            voice_lang=derive_voice_lang(config.character_config),
            # 名單（口頭禪、專有名詞）也要讀這次載入的角色，理由同上。
            character_config=config.character_config,
            # self.system_config 要到這個函式最後才換成新的；字幕翻成這次載入的
            # 「你看的語言」，不是上一份的。
            player_language=(
                config.system_config or self.system_config
            ).player_language,
        )

        # store typed config references
        self.config = config
        self.system_config = config.system_config or self.system_config
        self.character_config = config.character_config

    async def apply_persona(
        self,
        websocket: WebSocket,
        persona_id: str | None,
    ) -> None:
        """Hot-apply a persona preset without switching the active character.

        This intentionally keeps the current Live2D model, voice, conf_uid,
        conversation memory and history. The selected preset is persisted per
        character and becomes effective again after reconnect/restart.
        """
        from .persona_store import get_persona, set_active_persona

        clean_id = str(persona_id or "").strip() or None
        persona = get_persona(clean_id) if clean_id else None
        if clean_id and persona is None:
            raise ValueError("Persona not found.")

        prompt = (
            persona["prompt"] if persona is not None else self.character_persona_prompt
        )
        if not prompt:
            raise ValueError("Character default persona is unavailable.")

        effective_system_prompt = await self.construct_system_prompt(prompt)
        if self.agent_engine is None or not hasattr(self.agent_engine, "set_system"):
            raise RuntimeError(
                "The active conversation agent cannot switch persona live."
            )

        # Persist first only after every validation/build step has succeeded.
        set_active_persona(self.character_config.conf_uid, clean_id)
        self.character_config.persona_prompt = prompt
        if self.config is not None:
            self.config.character_config.persona_prompt = prompt
        self.agent_engine.set_system(effective_system_prompt)
        if hasattr(self.agent_engine, "set_persona"):
            # 人設原文也要跟著換，不然她的 background（背景工作讀的人設摘要）
            # 會停在舊的那個，跟剛換上的系統提示矛盾。
            self.agent_engine.set_persona(prompt)
        self.system_prompt = effective_system_prompt
        self.active_persona_id = clean_id

        await websocket.send_text(
            json.dumps(
                {
                    "type": "persona-switched",
                    "persona_id": clean_id,
                    "persona_name": persona["name"] if persona else None,
                }
            )
        )

    async def configure_stage_director(self, raw_candidates) -> list[dict[str, str]]:
        """Hot-apply a frontend-owned performance allowlist to the active LLM."""
        from .stage_director import (
            build_stage_director_prompt,
            normalize_stage_candidates,
        )

        candidates = normalize_stage_candidates(raw_candidates)
        self.stage_director_prompt = build_stage_director_prompt(candidates)
        if self.live2d_model is not None:
            self.live2d_model.stage_performance_ids = {
                item["id"] for item in candidates
            }

        if self.agent_engine is not None and hasattr(self.agent_engine, "set_system"):
            effective_system_prompt = await self.construct_system_prompt(
                self.character_config.persona_prompt
            )
            self.agent_engine.set_system(effective_system_prompt)
            if hasattr(self.agent_engine, "set_persona"):
                # 這裡不換人設，只是舞台表演清單變了；明講一次還是現在這個人設，
                # 不要讓它跟剛重組的系統提示脫鉤。
                self.agent_engine.set_persona(self.character_config.persona_prompt)
            self.system_prompt = effective_system_prompt
        return candidates

    def init_live2d(self, live2d_model_name: str) -> None:
        logger.info(f"Initializing Live2D: {live2d_model_name}")
        try:
            self.live2d_model = AvatarModel(live2d_model_name)
            self.character_config.live2d_model_name = live2d_model_name
        except Exception as e:
            logger.critical(f"Error initializing Live2D: {e}")
            logger.critical("Try to proceed without Live2D...")

    def init_asr(
        self, asr_config: ASRConfig, character_config: CharacterConfig | None = None
    ) -> None:
        # 系統層級「玩家語言」推導 ASR 辨識語言（best-effort）。目前 active 模型
        # sense_voice 只支援 zh/en/ja/ko/yue；clamp 後落在這個集合才覆寫 sherpa 的
        # language leaf，集合外（如法/德/西）回 'auto'，等於不強制 ＝ 維持原本辨識行為。
        # 語音路徑（translate_audio）完全不動。只動 sherpa_onnx_asr 這一個 engine。
        #
        # 角色聲音的語言 V 跟玩家語言推導出來的不一樣時（例：角色講日文、玩家語言是
        # 中文），不能把辨識鎖死在玩家語言——短句會被硬聽成玩家語言的諧音（實測：
        # pekora 講「おやすみなさい」被鎖中文的 SenseVoice 聽成「歐亞蘇明納賽」）。
        # 這種情況改成 'auto' 讓它自己偵測語言；V 沒設定、玩家語言本來就推不出明確
        # 語言（derived 已經是 'auto'）、或兩邊相同時，維持原本 clamp 行為不變。
        # character_config 沒傳進來時退回 self.character_config，跟改動前行為一致。
        #
        # 這段只對 sense_voice 模型生效：language 這個 leaf 只有 from_sense_voice
        # 會讀（sherpa_onnx_asr.py），其他 model_type 讀了也沒作用。
        #
        # 'yue'（廣東話）比較特殊：derive_voice_lang／_normalize_lang 沒有獨立的
        # yue bucket，廣東話聲音（GPT-SoVITS text_lang='yue'、edge zh-HK-*）一律
        # 算進 'zh'；但 _clamp_sense_voice_language 對 zh-HK / yue-* 玩家語言會回
        # 'yue'，跟 bucket 後的 'zh' 是同一件事。比較時把 'yue' 併回 'zh' 的桶，
        # 不然廣東話玩家對廣東話角色會被誤判成「語言不同」而跳成 auto。
        player_language = (
            getattr(self.system_config, "player_language", "") or ""
        ).strip()
        if player_language and asr_config.asr_model == "sherpa_onnx_asr":
            sherpa_block = getattr(asr_config, "sherpa_onnx_asr", None)
            if sherpa_block is not None:
                from .asr.sherpa_onnx_asr import VoiceRecognition as _SherpaASR

                derived = _SherpaASR._clamp_sense_voice_language(player_language)

                if getattr(sherpa_block, "model_type", None) == "sense_voice":
                    from .conversations.conversation_utils import derive_voice_lang

                    voice_lang = derive_voice_lang(
                        character_config
                        if character_config is not None
                        else self.character_config
                    )
                    derived_bucket = "zh" if derived == "yue" else derived
                    if (
                        voice_lang
                        and derived != "auto"
                        and voice_lang != derived_bucket
                    ):
                        logger.info(
                            f"ASR 語言：角色聲音語言 '{voice_lang}' 跟玩家語言推導出的 "
                            f"'{derived}' 不同，SenseVoice 改用 'auto' 自動偵測語言。"
                        )
                        derived = "auto"

                if derived != getattr(sherpa_block, "language", "auto"):
                    sherpa_block.language = derived
        if not self.asr_engine or (self.character_config.asr_config != asr_config):
            requested = asr_config.asr_model
            logger.info(f"Initializing ASR: {requested}")
            engine = None
            try:
                engine = ASRFactory.get_asr_system(
                    requested,
                    **getattr(asr_config, requested).model_dump(),
                )
            except Exception as e:
                # Voice input (the mic) is OPTIONAL. A missing or broken ASR engine
                # must NOT prevent the whole app from starting — that turns one bad
                # setting into "the app won't open at all". The usual cause is an
                # engine whose extra dependency isn't bundled (e.g. selecting
                # faster_whisper, which needs `pip install faster-whisper`). Fall back
                # to the bundled, offline sherpa_onnx_asr so voice still works; if even
                # that fails, disable voice input but keep text chat + voice output.
                logger.warning(
                    f"ASR engine '{requested}' failed to load ({type(e).__name__}: {e})."
                )
                fallback_block = getattr(asr_config, "sherpa_onnx_asr", None)
                if requested != "sherpa_onnx_asr" and fallback_block is not None:
                    try:
                        engine = ASRFactory.get_asr_system(
                            "sherpa_onnx_asr", **fallback_block.model_dump()
                        )
                        logger.warning(
                            "Fell back to the bundled 'sherpa_onnx_asr' for voice input."
                        )
                    except Exception as e2:
                        logger.warning(
                            f"Fallback ASR also failed ({type(e2).__name__}: {e2}). "
                            "Voice input disabled; text chat and voice output still work."
                        )
                else:
                    logger.warning(
                        "Voice input disabled; text chat and voice output still work."
                    )
            self.asr_engine = engine
            # saving config should be done after the initialization attempt
            self.character_config.asr_config = asr_config
        else:
            logger.info("ASR already initialized with the same config.")

    def init_tts(self, tts_config: TTSConfig) -> None:
        if not self.tts_engine or (self.character_config.tts_config != tts_config):
            requested = tts_config.tts_model
            logger.info(f"Initializing TTS: {requested}")
            engine = None
            try:
                engine = TTSFactory.get_tts_engine(
                    requested,
                    **getattr(tts_config, requested.lower()).model_dump(),
                )
            except Exception as e:
                # Voice OUTPUT must not brick the app. If the chosen TTS engine can't
                # load (missing dependency — e.g. bark/coqui/melo/x_tts — or an
                # unreachable external server), fall back to the bundled edge_tts so
                # the character still speaks; if even that fails, disable voice output
                # but keep text chat working. Never let this reach run()'s sys.exit(1).
                logger.warning(
                    f"TTS engine '{requested}' failed to load ({type(e).__name__}: {e})."
                )
                fallback_block = getattr(tts_config, "edge_tts", None)
                if requested.lower() != "edge_tts" and fallback_block is not None:
                    try:
                        engine = TTSFactory.get_tts_engine(
                            "edge_tts", **fallback_block.model_dump()
                        )
                        logger.warning(
                            "Fell back to the bundled 'edge_tts' for voice output."
                        )
                    except Exception as e2:
                        logger.warning(
                            f"Fallback TTS also failed ({type(e2).__name__}: {e2}). "
                            "Voice output disabled; text chat still works."
                        )
                else:
                    logger.warning("Voice output disabled; text chat still works.")
            self.tts_engine = engine
            self.character_config.tts_config = tts_config
        else:
            logger.info("TTS already initialized with the same config.")

    def init_vad(self, vad_config: VADConfig) -> None:
        if vad_config.vad_model is None:
            logger.info("VAD is disabled.")
            self.vad_engine = None
            return

        if not self.vad_engine or (self.character_config.vad_config != vad_config):
            logger.info(f"Initializing VAD: {vad_config.vad_model}")
            try:
                self.vad_engine = VADFactory.get_vad_engine(
                    vad_config.vad_model,
                    **getattr(vad_config, vad_config.vad_model.lower()).model_dump(),
                )
            except Exception as e:
                # VAD is optional — if it can't load, disable it instead of bricking
                # the app. (Voice activity detection just won't auto-segment speech.)
                logger.warning(
                    f"VAD engine '{vad_config.vad_model}' failed to load "
                    f"({type(e).__name__}: {e}). Disabling VAD (optional)."
                )
                self.vad_engine = None
            # saving config should be done after the initialization attempt
            self.character_config.vad_config = vad_config
        else:
            logger.info("VAD already initialized with the same config.")

    async def init_agent(
        self,
        agent_config: AgentConfig,
        persona_prompt: str,
        character_config: CharacterConfig | None = None,
    ) -> None:
        """Initialize or update the LLM engine based on agent configuration."""
        logger.info(f"Initializing Agent: {agent_config.conversation_agent_choice}")

        # During a character switch, load_from_config intentionally keeps the old
        # character on ``self`` until every engine has compared old vs new. Prompt
        # construction must nevertheless use the incoming character; otherwise a
        # character switch inherits the previous character's reply language, memory UID, avatar and TTS
        # preprocessor for the freshly-created agent.
        target_character = character_config or self.character_config

        if (
            character_config is None
            and self.agent_engine is not None
            and agent_config == self.character_config.agent_config
            and persona_prompt == self.character_config.persona_prompt
        ):
            logger.debug("Agent already initialized with the same config.")
            return

        system_prompt = await self.construct_system_prompt(
            persona_prompt,
            character_config=target_character,
        )

        # Pass avatar to agent factory
        avatar = target_character.avatar or ""  # Get avatar from config
        output_language = str(
            getattr(target_character, "reply_language", "")
            or getattr(self.system_config, "player_language", "")
            or ""
        )

        try:
            self.agent_engine = AgentFactory.create_agent(
                conversation_agent_choice=agent_config.conversation_agent_choice,
                agent_settings=agent_config.agent_settings.model_dump(),
                llm_configs=agent_config.llm_configs.model_dump(),
                system_prompt=system_prompt,
                live2d_model=self.live2d_model,
                tts_preprocessor_config=target_character.tts_preprocessor_config,
                character_avatar=avatar,
                system_config=self.system_config.model_dump(),
                output_language=output_language,
                tool_manager=self.tool_manager,
                tool_executor=self.tool_executor,
                mcp_prompt_string=self.mcp_prompt,
                # character_engine_agent 的狀態存在 chat_history/<conf_uid>/engine/。
                conf_uid=target_character.conf_uid,
                character_name=target_character.character_name,
                actions_enabled=bool(
                    getattr(target_character, "actions_enabled", False)
                ),
                # 記憶頁的開關：關掉時引擎也不再抽記憶、不再把記憶帶進對話。
                long_term_memory_enabled=target_character.long_term_memory_enabled,
                # 她的人設原文（逐字包在 system_prompt 裡）；給引擎的
                # CharacterProfile.background 讀，背景工作（情緒、心情…）才拿得到
                # 人設摘要，而不用讀整份系統提示。
                persona_prompt=persona_prompt,
            )

            logger.debug(f"Agent choice: {agent_config.conversation_agent_choice}")
            logger.debug(f"System prompt: {system_prompt}")

            # Save the current configuration
            target_character.agent_config = agent_config
            self.system_prompt = system_prompt

        except Exception as e:
            # The LLM "brain" is core to chatting, but a bad brain config must NOT
            # stop the app from OPENING — otherwise the user can't reach the settings
            # UI to fix it. Log clearly and leave the agent unset; the chat path
            # surfaces a friendly "set up your AI brain in Settings" notice.
            logger.error(
                f"Failed to initialize agent ({type(e).__name__}: {e}). The app will "
                "still open — open Settings to set up your AI brain."
            )
            self.agent_engine = None

        # 這個頁面現在拿的是這個 agent。
        self._follow_mood()

    def init_translate(
        self,
        translator_config: TranslatorConfig,
        voice_lang: str | None = None,
        player_language: str | None = None,
        character_config: CharacterConfig | None = None,
    ) -> None:
        """依設定建立或更新翻譯引擎。

        ``character_config`` 是這次要用的角色（換角色時是「新」角色；
        self.character_config 那時還是舊的）。沒給就用 self.character_config。
        翻譯器帶的口頭禪、專有名詞都從它讀，名單換了就重建引擎。

        Two independent engines are built from the SAME translator_config:
        - ``translate_engine``: AUDIO path (translates tts_text for the spoken voice).
          AUTOMATIC: this engine is now ALWAYS built (``translate_audio`` is an internal
          auto-on flag, not a user toggle). Whether a given sentence is actually
          translated is decided PER-SENTENCE in handle_sentence_output, by comparing the
          character's voice language V against the detected reply language R — translate
          only when V != R. So the engine being present no longer means "translate
          everything"; it just means the capability is ready.
          Its TARGET is now V (``voice_lang`` — the CHARACTER's voice language), mapped
          to the provider's expected format, so a reply in any language is spoken in the
          character's own voice language. The global per-conf target_lang stays only as
          a FALLBACK when V can't be derived. Rebuilt per character switch (this method
          re-runs on switch), so a new character's V takes effect immediately.
        - ``subtitle_translate_engine``: DISPLAY-ONLY path (translates the reply text
          for the on-screen subtitle). Built only when ``translate_subtitle`` is True.
          It targets the language you read (``player_language``) and NEVER mutates the canonical reply
          (memory/history stay on the original reply R).
        Subtitle may be disabled independently; disabled -> its engine is reset to None.
        """
        config_changed = (
            self.character_config.tts_preprocessor_config.translator_config
            != translator_config
        )
        # Rebuild the audio engine whenever V changes too, even if translator_config is
        # otherwise identical (e.g. two characters that share a translator block but
        # have different voice languages).
        voice_lang_changed = voice_lang != self._audio_translate_voice_lang
        # 字幕翻成「你看的語言」：它換了也要重建字幕引擎。
        player_language_changed = player_language != getattr(
            self, "_subtitle_player_language", None
        )
        # 角色的名單：兩個角色共用同一份翻譯設定、同一種語音語言時，只有名單
        # 不同——不比對它，上一個角色的引擎就會原封不動留下來。
        character = character_config or self.character_config
        protected_names = dict(getattr(character, "protected_names", None) or {})
        catchphrases = dict(getattr(character, "catchphrases", None) or {})
        audio_terms = (protected_names, catchphrases)
        audio_terms_changed = audio_terms != getattr(
            self, "_audio_translate_terms", None
        )
        # 字幕翻譯器也帶口頭禪，但寫法不換：來源寫法 → 來源寫法，原樣保留。
        # 目標寫法是為語音語言寫的，字幕翻成的是玩家看的語言。
        subtitle_catchphrases = {source: source for source in catchphrases}
        subtitle_terms = (protected_names, subtitle_catchphrases)
        subtitle_terms_changed = subtitle_terms != getattr(
            self, "_subtitle_terms", None
        )

        # --- AUDIO translation engine (now ALWAYS built; gate is per-sentence) ---
        # translate_audio is kept as an internal auto-on flag (always True in conf), so
        # the engine is always available; the V != R decision happens per sentence.
        if not translator_config.translate_audio:
            # 只有使用者手動把 translate_audio 設成 False 時才會走到這裡。
            logger.debug("Audio translation engine disabled (translate_audio=False).")
            self.translate_engine = None
            self._audio_translate_voice_lang = None
            self._audio_translate_terms = None
        elif (
            not self.translate_engine
            or config_changed
            or voice_lang_changed
            or audio_terms_changed
        ):
            provider = translator_config.translate_provider
            # Copy the provider block and override its target leaf with V (mapped per
            # provider). If V can't be derived/mapped, keep the conf's global target.
            audio_cfg = getattr(translator_config, provider).model_dump()
            mapped = self._map_voice_lang_to_provider_target(voice_lang, provider)
            if mapped is not None:
                if provider == "deeplx":
                    audio_cfg["deeplx_target_lang"] = mapped
                else:  # llm / tencent both use 'target_lang'
                    audio_cfg["target_lang"] = mapped
                logger.info(
                    f"Initializing audio Translator: {provider} -> "
                    f"V={voice_lang} (target={mapped})"
                )
            else:
                logger.info(
                    f"Initializing audio Translator: {provider} -> "
                    f"global target_lang (V={voice_lang} not mappable)"
                )
            self.translate_engine = TranslateFactory.get_translator(
                provider,
                audio_cfg,
                protected_names=protected_names,
                # 口頭禪的目標寫法是為語音語言寫的，只有這個引擎帶。
                catchphrases=catchphrases,
            )
            self._audio_translate_voice_lang = voice_lang
            self._audio_translate_terms = audio_terms
        else:
            logger.info("Audio translation already initialized with the same config.")

        # --- SUBTITLE translation engine (display-only) ---
        if not translator_config.translate_subtitle:
            logger.debug("Subtitle translation is disabled.")
            self.subtitle_translate_engine = None
        elif (
            not self.subtitle_translate_engine
            or config_changed
            or player_language_changed
            or subtitle_terms_changed
        ):
            logger.info(
                "Initializing subtitle Translator: "
                f"{translator_config.translate_provider} -> {player_language}"
            )
            self.subtitle_translate_engine = self._build_subtitle_translator(
                translator_config,
                player_language or "",
                protected_names,
                subtitle_catchphrases,
            )
            self._subtitle_player_language = player_language
            self._subtitle_terms = subtitle_terms
        else:
            logger.info(
                "Subtitle translation already initialized with the same config."
            )

        # 把可能更新過的設定參照存回去，只做一次。
        self.character_config.tts_preprocessor_config.translator_config = (
            translator_config
        )

    def _build_subtitle_translator(
        self,
        translator_config: TranslatorConfig,
        player_language: str,
        protected_names: dict[str, list[str]] | None = None,
        catchphrases: dict[str, str] | None = None,
    ) -> TranslateInterface | None:
        """給字幕另外建一個翻譯引擎。

        ``protected_names`` 是這次要用的角色的專有名詞（呼叫端從正在載入的角色
        讀出來）；沒給就讀 self.character_config。``catchphrases`` 是字幕要原樣
        保留的口頭禪（來源寫法 → 來源寫法）：口頭禪的目標寫法是為角色的語音語言
        寫的，字幕翻成的是玩家看的語言，但口頭禪本身不能被翻掉或音譯。

        Reuses the SAME provider as the audio path but overrides only the target
        language with the one you read (``player_language``) so the subtitle can differ from the
        spoken voice. The canonical reply is never touched by this engine; on any
        runtime error LLMTranslate already returns the original text (fail-soft).
        Returns None if it cannot be built (subtitle then falls back to the
        original reply R at call sites).
        """
        from .translate.deeplx import subtitle_target

        provider = translator_config.translate_provider
        # 字幕翻成「你看的語言」：跟 player_language 走，不是角色自己存的值。
        target = subtitle_target(player_language)
        if not target:
            logger.warning(
                "translate_subtitle is on but player_language is empty; "
                "subtitle translation disabled."
            )
            return None
        sub_block = getattr(translator_config, provider, None)
        if sub_block is None:
            logger.warning(
                f"translate_subtitle is on but provider '{provider}' block is "
                "missing; subtitle translation disabled."
            )
            return None
        # 複製供應商設定，只改目標語言那一個欄位。
        # 存下來的字幕語言是人看得懂的名字（例如「德文」），不是代碼——
        # llm engine can use it verbatim in its prompt. DeepL needs a target CODE,
        # so for deeplx we map the name -> code (resolver passes a real code
        # through unchanged, keeping hand-edited conf.yaml values working).
        cfg = sub_block.model_dump()
        if provider == "deeplx":
            from .translate.deeplx import resolve_deepl_target_lang

            cfg["deeplx_target_lang"] = resolve_deepl_target_lang(target)
        else:  # llm / tencent both use 'target_lang'
            cfg["target_lang"] = target
        if protected_names is None:
            protected_names = getattr(self.character_config, "protected_names", None)
        if catchphrases is None:
            catchphrases = {
                source: source
                for source in getattr(self.character_config, "catchphrases", None) or {}
            }
        try:
            return TranslateFactory.get_translator(
                provider,
                cfg,
                protected_names=protected_names,
                catchphrases=catchphrases,
            )
        except Exception as e:
            logger.warning(
                f"Could not build subtitle translator ({provider}): "
                f"{type(e).__name__}: {e}"
            )
            return None

    @staticmethod
    def _map_voice_lang_to_provider_target(
        voice_lang: str | None, provider: str
    ) -> str | None:
        """Map a short voice-language bucket V ('ja'/'zh'/'en'/'ko') to the target
        value the given provider expects. Returns None when V is empty/unknown so the
        caller falls back to the conf's global target_lang (fail-soft).

        - deeplx: needs a target CODE. Reuse the SAME name->code resolver the subtitle
          translator uses (resolve_deepl_target_lang); a plain code like 'JA' passes
          through unchanged.
        - llm: takes a HUMAN-READABLE label dropped into a Chinese prompt -> 日文/中文/...
        - tencent: takes a lowercase language code -> ja/zh/en/ko (== V already).
        """
        if not voice_lang:
            return None
        v = str(voice_lang).strip().lower()
        if v not in ("ja", "zh", "en", "ko"):
            return None
        provider = (provider or "").lower()
        if provider == "deeplx":
            # uppercased short codes; all in resolve_deepl_target_lang's known set
            from .translate.deeplx import resolve_deepl_target_lang

            return resolve_deepl_target_lang(v.upper())
        elif provider == "llm":
            return {"ja": "日文", "zh": "中文", "en": "English", "ko": "韓文"}[v]
        elif provider == "tencent":
            return v  # tencent uses lowercase codes
        return None

    # ==== utils

    async def construct_system_prompt(
        self,
        persona_prompt: str,
        character_config: CharacterConfig | None = None,
    ) -> str:
        """
        Append tool prompts to persona prompt.

        Parameters:
        - persona_prompt (str): The persona prompt.

        Returns:
        - str: The system prompt with all tool prompts appended.
        """
        logger.debug(f"constructing persona_prompt: '''{persona_prompt}'''")
        target_character = character_config or self.character_config

        # 共用的說話規則放最前面：放在後段時模型不太照做（見 SPEECH_RULES 的說明）。
        # 動作格式只給「可以寫動作描寫」的角色（見 ACTION_RULES 的說明）。
        from .conversation_quality import ACTION_RULES, SPEECH_RULES

        actions_enabled = bool(getattr(target_character, "actions_enabled", False))
        rules = SPEECH_RULES
        if actions_enabled:
            rules = f"{rules}\n\n{ACTION_RULES}"
        persona_prompt = f"{rules}\n\n{persona_prompt}"

        # 表情與動作由背景模型逐句挑（expression_pick）時，不教她寫標籤。
        # 「提示只增不改」顧的是同一模式下的快取；切模式本來就整段重讀。
        from .expression_pick import uses_background_expressions

        tags_by_background = uses_background_expressions(target_character)

        for prompt_name, prompt_file in self.system_config.tool_prompts.items():
            if tags_by_background and prompt_name in (
                "live2d_expression_prompt",
                "live2d_motion_prompt",
                "vrm_motion_prompt",
            ):
                continue

            if (
                prompt_name == "group_conversation_prompt"
                or prompt_name == "proactive_speak_prompt"
            ):
                continue

            # think_tag 提示在教角色寫動作；不寫動作的角色不附，免得被勾起來。
            if prompt_name == "think_tag_prompt" and not actions_enabled:
                continue

            # 模型載入失敗時 init_live2d 會留下 None 並「繼續跑」，這三份 prompt
            # 都在描述模型的表情與動作，沒有模型就沒有東西可教——而且下面每一條
            # 都會去讀 live2d_model 的屬性，不先跳過的話開機就直接炸掉。
            if self.live2d_model is None and prompt_name in (
                "live2d_motion_prompt",
                "vrm_motion_prompt",
                "live2d_expression_prompt",
            ):
                continue

            # 動作 prompt 分兩份，依模型類型擇一。兩者的動作清單形狀不同：
            # VRM 的每個關鍵字後面帶一句描述（來自 motionMap 的 label），
            # Live2D 那幾個模型只有 gesture_1／motion_2 這種沒有語意的名字。
            # 同一份說明沒辦法同時服務兩種——教 VRM「照描述挑」對 Live2D 是在
            # 講一個不存在的東西，教 Live2D「別猜泛用名稱」對 VRM 是廢話。
            if prompt_name in ("live2d_motion_prompt", "vrm_motion_prompt"):
                is_vrm = self.live2d_model.type == "vrm"
                wanted = "vrm_motion_prompt" if is_vrm else "live2d_motion_prompt"
                if prompt_name != wanted:
                    continue

            if (
                prompt_name in ("live2d_motion_prompt", "vrm_motion_prompt")
                and not self.live2d_model.motion_str
            ):
                # An empty motion_str means this model's motionMap has no
                # entries (or is missing entirely). Teaching the LLM a set of
                # keywords that will never match anything just burns tokens
                # and can make the tone stiffer for no benefit, so skip even
                # loading this prompt file in that case.
                continue

            if (
                prompt_name == "live2d_expression_prompt"
                and len(self.live2d_model.emo_map) < 2
            ):
                # Same reasoning as the motion guard above, for the case that
                # actually ships: a model whose emotionMap holds a single entry
                # (a hand-made rig can have only `neutral`). One keyword cannot express a
                # contrast — setting the sole expression is always a no-op — so
                # the prompt buys nothing. It is not merely wasted tokens: the
                # prompt says "use them regularly", the model complies, and the
                # emitted `[neutral]` reaches sentence_divider as content, which
                # splits one reply into an extra fragment that then costs its own
                # translate + TTS round trip. Observed in the logs as
                # `SentenceWithTags(text='[neutral]\n我这边反应有点延迟...')`.
                continue

            prompt_content = prompt_loader.load_util(prompt_file)

            if prompt_name == "live2d_expression_prompt":
                prompt_content = prompt_content.replace(
                    "[<insert_emomap_keys>]", self.live2d_model.emo_str
                )

            if prompt_name in ("live2d_motion_prompt", "vrm_motion_prompt"):
                prompt_content = prompt_content.replace(
                    "[<insert_motionmap_keys>]", self.live2d_model.motion_str
                )

            if prompt_name == "mcp_prompt":
                continue

            persona_prompt += prompt_content

        # 她記得什麼不放在系統提示裡：引擎把記憶寫進對話的備註。

        # Generic conversation quality belongs to the capability layer, not to any
        # character's personality.
        from .conversation_quality import CORE_CONVERSATION_PROMPT

        persona_prompt += f"\n\n{CORE_CONVERSATION_PROMPT}"
        if self.stage_director_prompt:
            persona_prompt += f"\n\n{self.stage_director_prompt}"

        # 系統層級「玩家語言」指令：設定後，無論輸入是什麼語言，所有角色都用玩家語言回覆。
        # 這是 system-level（套用所有角色），不寫進任何角色人設。放在最後讓它有最高權威性。
        # 正規回覆（= 字幕 + 對話紀錄 + 記憶）因此都會是玩家語言；語音另由 translate_audio 路徑
        # 翻成各角色 voice 語言（此處不動語音行為）。
        # 角色自己的 reply_language 優先，沒設才用全域的 player_language。
        # 語言屬於角色本身（日本角色講日文，貓娘不一定），全域設定只是「沒特別
        # 指定時的預設」。見 CharacterConfig.reply_language 的說明。
        character_language = (
            getattr(target_character, "reply_language", "") or ""
        ).strip()
        player_language = (
            character_language
            or (getattr(self.system_config, "player_language", "") or "")
        ).strip()
        if player_language:
            persona_prompt += (
                f"\n\n## Output language (system-level, overrides everything above)\n"
                f"Always write your reply in {player_language}, regardless of the "
                f"language the user speaks or types in. This applies to the entire "
                f"reply text. Do not switch languages even if the user uses another "
                f"language."
            )

        # 系統層級「玩家描述」指令：注入到所有角色的系統提示，描述玩家是誰、該怎麼稱呼他
        # （玩家永遠是同一個人）。和 player_language 一樣 system-level、不寫進任何角色人設；
        # handle_config_switch 會在切換角色時重讀 system_config，所以這裡會 hot-apply。
        player_prompt = getattr(self.system_config, "player_prompt", "") or ""
        if player_prompt:
            persona_prompt += (
                f"\n\n## About the player (applies to all characters)\n{player_prompt}"
            )

        logger.debug("\n === System Prompt ===")
        logger.debug(persona_prompt)

        return persona_prompt

    async def load_character_config(self, config_file_name: str) -> None:
        """Load one character without sending WebSocket notifications."""
        base_config_data = read_yaml("conf.yaml")
        base_character_data = base_config_data.get("character_config")
        if not isinstance(base_character_data, dict):
            raise ValueError("Base character configuration is missing")

        if config_file_name == "conf.yaml":
            new_character_config_data = base_character_data
        else:
            # Mirror character_route._safe_character_path: reject path
            # separators / non-.yaml names, then confirm the normalized path
            # stays inside config_alts_dir (blocks '../' escapes).
            characters_dir = self.system_config.config_alts_dir
            if (
                not config_file_name
                or os.path.basename(config_file_name) != config_file_name
                or not config_file_name.endswith(".yaml")
            ):
                raise ValueError("Invalid configuration file path")

            base = os.path.normpath(os.path.abspath(characters_dir))
            file_path = os.path.normpath(
                os.path.abspath(os.path.join(characters_dir, config_file_name))
            )
            if not (file_path == base or file_path.startswith(base + os.sep)):
                raise ValueError("Invalid configuration file path")

            alt_config_data = read_yaml(file_path).get("character_config")
            if not isinstance(alt_config_data, dict):
                raise ValueError(
                    f"Character configuration is missing: {config_file_name}"
                )

            # Older Character Manager files may not include character_name.
            if alt_config_data.get("conf_name") and not alt_config_data.get(
                "character_name"
            ):
                alt_config_data["character_name"] = alt_config_data["conf_name"]

            # Always merge against the on-disk base, never the previously active
            # character. Otherwise switching A -> B leaks omitted A settings into B.
            new_character_config_data = deep_merge(
                base_character_data, with_conversation_block(alt_config_data)
            )

        new_config = validate_config(
            {
                "system_config": base_config_data.get("system_config")
                or self.system_config.model_dump(),
                "character_config": new_character_config_data,
            }
        )
        await self.load_from_config(new_config)
        self.active_config_file = config_file_name

    async def _send_model_and_conf(self, websocket: WebSocket) -> None:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "set-model-and-conf",
                    "model_info": self.live2d_model.model_info,
                    "conf_name": self.character_config.conf_name,
                    "conf_uid": self.character_config.conf_uid,
                }
            )
        )
        # 換角色、重新載入之後，臉馬上帶著她現在的心情。
        await send_character_mood(
            getattr(self, "agent_engine", None), websocket.send_text
        )

    async def handle_config_reload(self, websocket: WebSocket) -> bool:
        """用磁碟上的設定重新載入目前的角色，不換角色。

        跟 handle_config_switch 差在回給前端的是 config-reloaded 而不是
        config-switched：前端收到後者會跳「角色已切換」並開一段新對話，存個設定
        不該有這些副作用。失敗時只回錯誤、不往外丟，連線要留著。
        """
        file_name = self.active_config_file or "conf.yaml"
        try:
            await self.load_character_config(file_name)
            await self._send_model_and_conf(websocket)
            await websocket.send_text(
                json.dumps({"type": "config-reloaded", "file": file_name})
            )
            logger.info(f"Configuration reloaded from {file_name}")
            return True
        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Error reloading configuration: {str(e)}",
                    }
                )
            )
            return False

    async def handle_config_switch(
        self,
        websocket: WebSocket,
        config_file_name: str,
    ) -> bool:
        """Switch character, persist the selection, and notify the client."""
        try:
            await self.load_character_config(config_file_name)

            # Persist only after the new config has loaded successfully. This state
            # is consumed on both server restart and WebSocket reconnect.
            from .active_character_store import set_active_character_filename

            try:
                set_active_character_filename(config_file_name)
            except OSError as e:
                # A read-only disk should not leave the live session half-switched
                # with no success response. The selection simply cannot survive the
                # next restart in that exceptional case.
                logger.warning(
                    f"Could not persist active character ({type(e).__name__}: {e})"
                )
            logger.debug(f"New config: {self}")
            logger.debug(f"New character config: {self.character_config.model_dump()}")

            # Send responses to client
            await self._send_model_and_conf(websocket)

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "config-switched",
                        "message": f"Switched to config: {config_file_name}",
                        "file": config_file_name,
                    }
                )
            )

            logger.info(f"Configuration switched to {config_file_name}")
            return True
        except Exception as e:
            logger.error(f"Error switching configuration: {e}")
            logger.debug(self)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Error switching configuration: {str(e)}",
                    }
                )
            )
            raise e


def deep_merge(dict1, dict2):
    """
    Recursively merges dict2 into dict1, prioritizing values from dict2.
    """
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
