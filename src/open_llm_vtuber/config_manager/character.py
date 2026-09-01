# config_manager/character.py
from pydantic import Field, field_validator
from typing import Dict, ClassVar
from .i18n import I18nMixin, Description
from .asr import ASRConfig
from .tts import TTSConfig
from .vad import VADConfig
from .tts_preprocessor import TTSPreprocessorConfig

from .agent import AgentConfig


class CharacterConfig(I18nMixin):
    """Character configuration settings."""

    conf_name: str = Field(..., alias="conf_name")
    conf_uid: str = Field(..., alias="conf_uid")
    live2d_model_name: str = Field(..., alias="live2d_model_name")
    character_name: str = Field(default="", alias="character_name")
    human_name: str = Field(default="Human", alias="human_name")
    avatar: str = Field(default="", alias="avatar")
    # Danbooru character tag used when she draws herself, e.g. "makise kurisu".
    # animagine-xl-4.0 is danbooru-trained, so this one tag pins her appearance
    # far better than any description — measured, the 9B's own attempts at her
    # looks were wrong every time (glasses, short hair, white hair). Empty means
    # the character simply has no self-portrait route; nothing breaks.
    persona_prompt: str = Field(..., alias="persona_prompt")
    agent_config: AgentConfig = Field(..., alias="agent_config")
    asr_config: ASRConfig = Field(..., alias="asr_config")
    tts_config: TTSConfig = Field(..., alias="tts_config")
    vad_config: VADConfig = Field(..., alias="vad_config")
    tts_preprocessor_config: TTSPreprocessorConfig = Field(
        ..., alias="tts_preprocessor_config"
    )
    # 長期記憶的總開關。關掉會同時停掉整理與注入。
    # behavior for confs that don't set this key. When False: skip consolidation
    long_term_memory_enabled: bool = Field(
        default=True, alias="long_term_memory_enabled"
    )
    # 記憶的字數上限。越大記得越多，但每輪的 token 也越多、整理時越容易漏掉東西。
    # that don't set this key. Bigger = remembers more but more tokens/turn + slower
    # + lossier consolidation. Bounded to [500, 8000] by the validator below.
    core_memory_max_chars: int = Field(default=1500, alias="core_memory_max_chars")
    # 這個角色說話用的語言。留空＝沿用 system_config.player_language。
    #
    # 為什麼要在角色層級：player_language 是全域的，設成日文會讓每一個角色都
    # 講日文。但語言屬於角色本身——牧瀨紅莉栖是日本人，貓娘不是。全域設定該
    # 是「沒特別指定時的預設」，不是「所有人都得照做」。
    #
    # 跟 tts_config 的 text_lang 是兩件事：這裡是「她用什麼語言想事情、寫回覆」
    # （R），text_lang 是「用什麼語言發聲」（V）。兩者不同時，語音路徑會先翻譯
    # 再合成；相同時直接唸，省下一次翻譯。
    reply_language: str = Field(default="", alias="reply_language")
    # 這個角色的專有名詞：正式寫法 → 要被折回去的錯誤寫法。
    #
    # 兩件事會破壞專有名詞：小模型會把名字換成同音字（實測反覆發生，即使
    # prompt 已經明講不可以），而 OpenCC 的 s2twp 會把名字裡的某個字當成一般
    # 詞彙做台灣用語轉換。兩者都需要在輸出端把正確寫法確定性地釘回去。
    #
    # 為什麼放在角色層級而不是寫在引擎裡：要保護哪些名字屬於角色，不屬於這個
    # app。引擎內建特定作品的角色名字，等於每個使用者的安裝都帶著別人的角色。
    # 留空（預設）＝不保護任何名字，行為與沒有這個功能時完全相同。
    protected_names: dict[str, list[str]] = Field(
        default_factory=dict, alias="protected_names"
    )
    # 每幾輪整理一次記憶。3 或 5 可以把整理用的呼叫省一半以上，適合弱機。
    # (every turn) preserves existing behavior. 3/5 halve+ the "tidy-up" LLM calls for
    # weak/local models. Clamped to {1,3,5} by the validator below (fail-soft -> 1).
    memory_consolidation_interval: int = Field(
        default=1, alias="memory_consolidation_interval"
    )

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "conf_name": Description(
            en="Name of the character configuration", zh="角色配置名称"
        ),
        "conf_uid": Description(
            en="Unique identifier for the character configuration",
            zh="角色配置唯一标识符",
        ),
        "live2d_model_name": Description(
            en="Name of the Live2D model to use", zh="使用的Live2D模型名称"
        ),
        "character_name": Description(
            en="Name of the AI character in conversation", zh="对话中AI角色的名字"
        ),
        "persona_prompt": Description(
            en="Persona prompt. The persona of your character.", zh="角色人设提示词"
        ),
        "agent_config": Description(
            en="Configuration for the conversation agent", zh="对话代理配置"
        ),
        "asr_config": Description(
            en="Configuration for Automatic Speech Recognition", zh="语音识别配置"
        ),
        "tts_config": Description(
            en="Configuration for Text-to-Speech", zh="语音合成配置"
        ),
        "vad_config": Description(
            en="Configuration for Voice Activity Detection", zh="语音活动检测配置"
        ),
        "tts_preprocessor_config": Description(
            en="Configuration for Text-to-Speech Preprocessor",
            zh="语音合成预处理器配置",
        ),
        "human_name": Description(
            en="Name of the human user in conversation", zh="对话中人类用户的名字"
        ),
        "avatar": Description(
            en="Avatar image path for the character", zh="角色头像图片路径"
        ),
        "long_term_memory_enabled": Description(
            en="Enable long-term (core) memory: consolidation + injection",
            zh="啟用長期（核心）記憶：整理 + 注入",
        ),
        "core_memory_max_chars": Description(
            en="Core memory size cap in characters (500-8000, default 1500). "
            "Bigger = more tokens/turn + slower + lossier consolidation.",
            zh="核心記憶字數上限（500–8000，預設 1500）。"
            "越大越能記、但每輪 token 越多、整理舊記憶更易遺漏。",
        ),
        "memory_consolidation_interval": Description(
            en="Consolidate core memory every N turns (1/3/5, default 1=every turn). "
            "3/5 cut the tidy-up LLM calls roughly in half for weak/local models.",
            zh="每幾輪整理一次核心記憶（1/3/5，預設 1=每輪）。"
            "3/5 可把整理用的 LLM 呼叫省一半以上，適合弱機或本地模型。",
        ),
    }

    @field_validator("core_memory_max_chars")
    def clamp_core_memory_max_chars(cls, v):
        # 夾界的規則要跟 memory_core 一致，否則載入時與執行時對同一個值的看法會不同。
        # the default on any bad value rather than rejecting the whole config.
        try:
            n = int(v)
        except (TypeError, ValueError):
            return 1500
        return max(500, min(8000, n))

        try:
            n = int(v)
        except (TypeError, ValueError):
            return 3
        return max(1, min(10, n))

    @field_validator("memory_consolidation_interval")
    def clamp_memory_consolidation_interval(cls, v):
        # 夾進允許的集合；壞值一律回 1（每輪整理，最保守）。
        # behavior) on any bad value rather than rejecting the whole config.
        try:
            n = int(v)
        except (TypeError, ValueError):
            return 1
        return n if n in (1, 3, 5) else 1

    @field_validator("persona_prompt")
    def check_default_persona_prompt(cls, v):
        if not v:
            raise ValueError(
                "Persona_prompt cannot be empty. Please provide a persona prompt."
            )
        return v

    @field_validator("character_name")
    def set_default_character_name(cls, v, info):
        # 沒有顯示名就用設定名——空的話畫面會顯示寫死的「AI」。
        # in info.data). pydantic v2 passes a ValidationInfo, not a values dict.
        if not v:
            return info.data.get("conf_name", v)
        return v
