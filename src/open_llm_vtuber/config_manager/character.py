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
    # Danbooru character tag used when she draws herself, e.g. "your_character_name".
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
    # 這個角色要不要有長期記憶（引擎記住你說過的事、她自己說過的事）。
    # 關掉時引擎不抽取、不帶進對話。
    long_term_memory_enabled: bool = Field(
        default=True, alias="long_term_memory_enabled"
    )
    # 這個角色可不可以在台詞裡搭配動作描寫（*把視線移開*）。開著才把動作格式與
    # think_tag 提示接進系統提示；關著提示裡完全不提動作。
    actions_enabled: bool = Field(default=False, alias="actions_enabled")
    # 雙語字幕：畫面字幕多一行她實際唸出來的那句（語音翻譯後的原文），原本的
    # 字幕在下一行。只影響畫面；對話紀錄與記憶照舊只存回覆原文。預設關。
    bilingual_subtitle: bool = Field(default=False, alias="bilingual_subtitle")
    # 這個角色說話用的語言。留空＝沿用 system_config.player_language。
    #
    # 為什麼要在角色層級：player_language 是全域的，設成日文會讓每一個角色都
    # 講日文。但語言屬於角色本身——日本角色講日文，貓娘不一定。全域設定該
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
    # 這個角色的口頭禪：來源寫法 → 翻譯到目標語言時要用的寫法。
    #
    # 音訊翻譯器（把回覆轉成她的語音語言）逐句翻譯時，句尾的口頭禪（例如中文裡的
    # 「nya」）常常被當成贅字直接丟掉——它不是一般詞彙，翻譯模型沒有理由保留。
    # 這份對照表會被寫進翻譯器的 system prompt，交代「這個詞要照這樣寫，不要丟掉
    # 也不要意譯」。
    #
    # 跟 protected_names 不同：protected_names 保護的是輸出端的簡繁／同音字錯誤，
    # 任何目標語言都可能發生；catchphrases 的值是寫給某一個特定目標語言的（通常
    # 就是這個角色的語音語言），所以只接到翻譯目標真的是那個語言的翻譯器上才有
    # 意義。留空（預設）＝不保留任何口頭禪，行為與沒有這個功能時完全相同。
    catchphrases: dict[str, str] = Field(default_factory=dict, alias="catchphrases")

    DESCRIPTIONS: ClassVar[Dict[str, Description]] = {
        "actions_enabled": Description(
            en="Whether this character may add a short action between asterisks",
            zh="這個角色可不可以在台詞裡搭配一句星號包起來的動作描寫",
        ),
        "bilingual_subtitle": Description(
            en="Show the line she actually speaks above the subtitle (two lines)",
            zh="字幕顯示兩行：上行是她實際唸的原文，下行是原本的字幕",
        ),
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
            en="Long-term memory for this character: the engine remembers what you "
            "said and what she said. Off = nothing is extracted or brought back.",
            zh="這個角色要不要有長期記憶（引擎記住你說過的事、她自己說過的事）。"
            "關掉時引擎不抽取、不帶進對話。",
        ),
    }

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
